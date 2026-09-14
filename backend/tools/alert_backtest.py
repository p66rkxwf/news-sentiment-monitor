"""情緒預警歷史回測：系統有沒有在事件「之前」示警？依 docs/alert_backtest_prereg.md 的預先聲明執行。

用法（backend/ 目錄執行）:
    python tools/alert_backtest.py events               # 依價格規則選出事件、估算請求數（不抓新聞、不評分）
    python tools/alert_backtest.py run                  # 回補新聞 → 評分 → 逐日判斷 → docs/alert_backtest.md
    python tools/alert_backtest.py run --only 2357.TW   # 試跑（寫到 docs/alert_backtest_trial.md，正式報告須全跑）

三個設計，專門防「回測看起來很準」的常見陷阱：
1. 事件由價格規則機械式選出，不是挑我們記得的新聞——挑過的樣本必然偏向「有明顯利空新聞」的事件。
   手挑的敘事型事件另列一節、不併入統計。
2. 「事前」只算開盤前可得的標題（inference/alerts.py 的資訊時點規則）。事件日當天的開盤前示警
   另計：跳空開低時投資人其實來不及反應，那是「即時」而不是「提前」。
3. 背景警示率：同批股票在事件前第 10～6 個交易日的警示頻率 p。事件前 5 個交易日純靠運氣
   至少響一次的機率是 1 − (1 − p)^5；事前命中率沒有明顯高於它，就不能宣稱系統能提前預警。
"""

from __future__ import annotations

import argparse
import math
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from newssent.config import (  # noqa: E402
    ALERT_BASELINE_SESSIONS,
    ALERT_LLM_MODEL,
    ALERT_SCORE_DB_PATH,
    ALERT_UNIVERSE,
    FINMIND_TOKEN,
)
from newssent.data.finmind_news import FINMIND_API_URL, FINMIND_PROVIDER, FinMindNewsClient  # noqa: E402
from newssent.data.score_store import ScoreStore, utc_days  # noqa: E402
from newssent.inference.alert_board import TickerAlert, assess_ticker  # noqa: E402
from newssent.inference.alert_recorder import record  # noqa: E402
from newssent.inference.alerts import MARKET_TZ, AlertLevel, AlertParams  # noqa: E402

DOCS_DIR = BACKEND_ROOT.parent / "docs"

# --- 預先聲明的規則：改任何一項都必須先改 docs/alert_backtest_prereg.md 並 commit，再重跑 ---
PERIOD_START = date(2024, 9, 1)   # gemma3:27b 知識截止約 2024-08：更早的事件，評分器可能讀過事後報導
PERIOD_END = date(2025, 12, 31)
ABNORMAL_MAX = -0.07              # 個股報酬 − 加權指數報酬
RAW_MAX = -0.05                   # 個股自己也要真的跌（排除「大盤大漲、防禦股沒跟上」）
DEDUPE_SESSIONS = 20              # 同一檔 20 個交易日內只取第一次（同一波下跌不重複計）
PRE = range(-5, 0)                # 「事前」＝事件日前 5 個交易日
BACKGROUND = range(-10, -5)       # 背景期＝事件日前第 10～6 個交易日
TIMELINE = range(-10, 1)
LOOKBACK = 10 + ALERT_BASELINE_SESSIONS + 1   # 最早評估日所需的交易日（基準 20＋左邊界 1）
TRIGGERED = (AlertLevel.HIGH, AlertLevel.WATCH)
FINMIND_INTERVAL = 6.5 if FINMIND_TOKEN else 12.5


@dataclass(frozen=True)
class Event:
    ticker: str
    session: date
    kind: str        # "rule"＝價格規則選出（計入統計）｜"narrative"＝手挑（只展示）
    label: str = ""


# 手挑的敘事型事件：demo 常被問到、資訊在休市期間發酵。**不併入統計**。
NARRATIVE = [
    Event("2382.TW", date(2025, 2, 3), "narrative", "DeepSeek＋北美關稅，春節休市 11 天期間發酵"),
    Event("2317.TW", date(2025, 4, 7), "narrative", "川普對等關稅 32%，清明連假休市期間宣布"),
    Event("2882.TW", date(2025, 5, 5), "narrative", "新台幣單月急升，壽險匯損"),
]


@dataclass
class EventResult:
    event: Event
    raw: float | None
    abnormal: float | None
    car5: float | None
    timeline: dict[int, TickerAlert]   # 相對事件日的交易日位移 → 判斷結果


# --- 價格與事件選取 ---


def load_prices():
    import yfinance as yf

    close = yf.download(
        list(ALERT_UNIVERSE) + ["^TWII"],
        start=(PERIOD_START - timedelta(days=120)).isoformat(),
        end=(PERIOD_END + timedelta(days=20)).isoformat(),
        auto_adjust=True,
        progress=False,
    )["Close"]
    close = close.loc[close["^TWII"].notna()]
    sessions = [ts.date() for ts in close.index]
    rets = close.pct_change(fill_method=None)
    market = rets.pop("^TWII")
    return rets, market, sessions


def ex_right_dates(stock_id: str) -> set[date]:
    """除權息日。實測 yfinance 還原價沒處理到台灣大 2024-07-08 的除息，當天的「跌」只是配息。"""
    import httpx

    time.sleep(FINMIND_INTERVAL)
    headers = {"Authorization": f"Bearer {FINMIND_TOKEN}"} if FINMIND_TOKEN else {}
    resp = httpx.get(
        FINMIND_API_URL,
        params={
            "dataset": "TaiwanStockDividendResult",
            "data_id": stock_id,
            "start_date": PERIOD_START.isoformat(),
            "end_date": PERIOD_END.isoformat(),
        },
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    return {date.fromisoformat(row["date"]) for row in resp.json().get("data") or []}


def select_events(rets, market, sessions: list[date]) -> list[Event]:
    abnormal = rets.sub(market, axis=0)
    pos = {s: i for i, s in enumerate(sessions)}
    candidates: dict[str, list[date]] = {}
    for ts in abnormal.index:
        day = ts.date()
        if not PERIOD_START <= day <= PERIOD_END:
            continue
        for ticker in abnormal.columns:
            if abnormal.at[ts, ticker] <= ABNORMAL_MAX and rets.at[ts, ticker] <= RAW_MAX:
                candidates.setdefault(ticker, []).append(day)

    events: list[Event] = []
    for ticker, days in sorted(candidates.items()):
        excluded = ex_right_dates(ticker.split(".")[0])
        kept: date | None = None
        for day in sorted(days):
            if day in excluded:
                continue
            if kept is not None and pos[day] - pos[kept] < DEDUPE_SESSIONS:
                continue
            events.append(Event(ticker, day, "rule"))
            kept = day
    return sorted(events, key=lambda e: (e.session, e.ticker))


def _num(value) -> float | None:
    return None if value is None or math.isnan(value) else float(value)


def price_stats(event: Event, rets, market, sessions: list[date]) -> tuple[float | None, float | None, float | None]:
    i = sessions.index(event.session)
    stock = rets[event.ticker]
    raw = _num(stock.iloc[i])
    abnormal = None if raw is None else raw - float(market.iloc[i])
    car5 = _num((stock.iloc[i: i + 5] - market.iloc[i: i + 5]).sum(min_count=5))
    return raw, abnormal, car5


# --- 子指令 ---


def cmd_events(events: list[Event], rets, market, sessions: list[date]) -> None:
    store = ScoreStore(ALERT_SCORE_DB_PATH)
    pending: set[tuple[str, date]] = set()
    try:
        print(f"{'股票':<9}{'名稱':<8}{'事件日':<12}{'當日':>7}{'異常':>7}  類型")
        for event in events:
            raw, abnormal, _ = price_stats(event, rets, market, sessions)
            i = sessions.index(event.session)
            done = store.fetched_days(event.ticker, FINMIND_PROVIDER)
            pending |= {
                (event.ticker, d) for d in utc_days(sessions[max(0, i - LOOKBACK)], event.session) if d not in done
            }
            print(
                f"{event.ticker:<9}{ALERT_UNIVERSE[event.ticker]:<8}{event.session!s:<12}"
                f"{_pct(raw):>7}{_pct(abnormal):>7}  {event.kind} {event.label}"
            )
    finally:
        store.close()
    hours = len(pending) * FINMIND_INTERVAL / 3600
    print(f"\n待抓 {len(pending)} 個 (股票, UTC 日)：FinMind 約 {hours:.1f} 小時；LLM 評分另計（每則約 2–4 秒）")


def cmd_run(events: list[Event], rets, market, sessions: list[date], model: str, out_path: Path) -> None:
    from newssent.inference.llm_review import OllamaReviewer
    from newssent.inference.scorers import LlmScorer

    reviewer = OllamaReviewer(model=model)
    if not reviewer.available():
        raise SystemExit(f"本機 Ollama 沒有模型 {model}（或 Ollama 未啟動）")
    scorer = LlmScorer(reviewer)
    client = FinMindNewsClient(token=FINMIND_TOKEN)
    params = AlertParams()

    store = ScoreStore(ALERT_SCORE_DB_PATH)
    results: list[EventResult] = []
    try:
        store.save_sessions(sessions)
        for n, event in enumerate(events, 1):
            i = sessions.index(event.session)
            name = ALERT_UNIVERSE[event.ticker]
            if i < LOOKBACK:
                print(f"[{n}/{len(events)}] 略過 {event.ticker} {event.session}：價格資料不足以建立基準期")
                continue
            print(f"[{n}/{len(events)}] {event.ticker} {name} {event.session}")
            record(store, client, scorer, {event.ticker: name}, sessions[i - LOOKBACK], event.session)
            timeline = {
                k: assess_ticker(store, event.ticker, name, scorer.version, sessions, sessions[i + k], params)
                for k in TIMELINE
            }
            results.append(EventResult(event, *price_stats(event, rets, market, sessions), timeline))
    finally:
        store.close()

    out_path.write_text(render_report(results, scorer.version, params), encoding="utf-8")
    print(f"報告已寫入 {out_path}")


# --- 報告 ---


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:+.1%}"


def _level(alert: TickerAlert) -> AlertLevel:
    return alert.assessment.level


def _cell(alert: TickerAlert) -> str:
    a = alert.assessment
    if a.level is AlertLevel.INSUFFICIENT:
        return "—"
    return f"{a.z:+.1f}" + {AlertLevel.HIGH: "🔴", AlertLevel.WATCH: "🟡"}.get(a.level, "")


def binom_sf(k: int, n: int, p: float) -> float:
    """P(X ≥ k)，X ~ Binomial(n, p)：隨機響鈴下至少命中 k 次的機率。"""
    return sum(math.comb(n, j) * p**j * (1 - p) ** (n - j) for j in range(k, n + 1))


def _timeline_table(results: list[EventResult]) -> list[str]:
    header = "| 股票 | 事件日 | 當日 | 異常 | 5日CAR | " + " | ".join(
        "E" if k == 0 else f"E{k}" for k in TIMELINE
    ) + " |"
    lines = [header, "|" + "---|" * (5 + len(TIMELINE))]
    for r in results:
        e = r.event
        cells = " | ".join(_cell(r.timeline[k]) for k in TIMELINE)
        lines.append(
            f"| {e.ticker} {ALERT_UNIVERSE[e.ticker]} | {e.session} | {_pct(r.raw)} | {_pct(r.abnormal)} "
            f"| {_pct(r.car5)} | {cells} |"
        )
    return lines


def _evidence_lines(results: list[EventResult]) -> list[str]:
    lines: list[str] = []
    for r in results:
        first = next((k for k in TIMELINE if _level(r.timeline[k]) in TRIGGERED), None)
        e = r.event
        lines.append(f"### {e.ticker} {ALERT_UNIVERSE[e.ticker]}（事件日 {e.session}）")
        if first is None:
            day0 = r.timeline[0].assessment
            why = day0.reason if day0.level is AlertLevel.INSUFFICIENT else f"事件日 z = {day0.z:+.2f}"
            lines += [f"- 事件日前 10 個交易日至事件日皆未示警（{why}）", ""]
            continue
        alert = r.timeline[first]
        a = alert.assessment
        lines.append(
            f"- 首次示警：{a.session}（{'E' if first == 0 else f'E{first}'}），"
            f"{a.level.value}，z = {a.z:+.2f}，當日 {a.n} 則標題"
        )
        for ev in alert.evidence:
            when = ev.published_at.astimezone(MARKET_TZ).strftime("%m-%d %H:%M")
            lines.append(f"  - 「{ev.title}」— {ev.source}（台北 {when}）")
        lines.append("")
    return lines


def render_report(results: list[EventResult], scorer: str, params: AlertParams) -> str:
    rule = [r for r in results if r.event.kind == "rule"]
    narrative = [r for r in results if r.event.kind == "narrative"]

    pre_eval = [r for r in rule if any(_level(r.timeline[k]) is not AlertLevel.INSUFFICIENT for k in PRE)]
    pre_hits = [r for r in pre_eval if any(_level(r.timeline[k]) in TRIGGERED for k in PRE)]
    day_eval = [r for r in rule if _level(r.timeline[0]) is not AlertLevel.INSUFFICIENT]
    day_hits = [r for r in day_eval if _level(r.timeline[0]) in TRIGGERED]
    background = [
        _level(r.timeline[k]) for r in rule for k in BACKGROUND if _level(r.timeline[k]) is not AlertLevel.INSUFFICIENT
    ]
    bg_hits = sum(level in TRIGGERED for level in background)
    p = bg_hits / len(background) if background else None
    chance = None if p is None else 1 - (1 - p) ** len(PRE)
    sf = None if chance is None or not pre_eval else binom_sf(len(pre_hits), len(pre_eval), chance)

    if sf is None or len(pre_eval) < 5:
        verdict = "事前窗可評估的事件少於 5 件（或無背景樣本），資料不足，不做推論。"
    elif sf < 0.05:
        verdict = (
            f"事前示警率高於隨機響鈴的預期（單尾二項 p = {sf:.3f}）。事件數 n = {len(pre_eval)} 仍小，"
            "應視為初步證據，不是已驗證的預測能力。"
        )
    else:
        verdict = (
            f"事前示警率與隨機響鈴無法區分（單尾二項 p = {sf:.3f}）——**不能宣稱系統能提前預警**。"
            "可以誠實呈現的是事件日開盤前的即時示警率，以及觸發當下的證據標題。"
        )

    now = datetime.now(timezone.utc)
    lines = [
        "# 情緒異常預警：歷史回測",
        "",
        f"> 產出 {now:%Y-%m-%d %H:%M} UTC｜評分器 `{scorer}`｜z < {params.watch_z} 為 watch、"
        f"z < {params.high_z} 為 high｜基準 {params.baseline_sessions} 個交易日",
        "> 依 [預先聲明](alert_backtest_prereg.md) 執行。新聞為 FinMind **事後回補**：發布時間是資料源宣稱的，"
        "不等於當時系統真的抓得到（事後刪除的新聞不會出現）。",
        "> 盤勢報導標題（`config.ALERT_PRICE_REPORT_PATTERNS`）不評分、不計入分數。",
        "",
        "## 一、主結論（只計價格規則選出的事件）",
        "",
        "| 指標 | 結果 |",
        "|---|---|",
        f"| 規則選出事件數 | {len(rule)} |",
        f"| 事前 5 個交易日內至少示警一次 | {len(pre_hits)} / {len(pre_eval)}（事前窗有資料者） |",
        f"| 事件日開盤前示警（即時，非提前） | {len(day_hits)} / {len(day_eval)} |",
        f"| 背景警示率 p（事件前第 10～6 個交易日） | "
        + ("—" if p is None else f"{p:.1%}（{bg_hits} / {len(background)} 個股票日）")
        + " |",
        "| 隨機響鈴下事前至少一次的機率 1 − (1 − p)⁵ | " + ("—" if chance is None else f"{chance:.1%}") + " |",
        "| 單尾二項檢定 | " + ("—" if sf is None else f"p = {sf:.3f}") + " |",
        "",
        f"**判讀**：{verdict}",
        "",
        "## 二、逐事件 z 值軌跡（🔴 high、🟡 watch、— 資料不足）",
        "",
        *_timeline_table(rule),
        "",
        "## 三、首次示警的證據標題",
        "",
        *_evidence_lines(rule),
        "## 四、敘事型事件（手挑，不併入第一節統計）",
        "",
    ]
    if narrative:
        lines += [*_timeline_table(narrative), "", *_evidence_lines(narrative)]
        lines += [f"- {r.event.ticker} {r.event.session}：{r.event.label}" for r in narrative]
    else:
        lines.append("（本次未執行）")
    lines += [
        "",
        "## 五、限制",
        "",
        "- 事件數少；背景期緊鄰事件，事前醞釀會同時抬高背景警示率，使檢定偏保守。",
        "- 評分器是本機 LLM 的 one-hot 標籤，未經台股中文標題的人工標注驗證。",
        "- 異常報酬以單日「個股 − 加權指數」近似，未做 beta 調整。",
        "- 價格下跌不一定有新聞原因；沒有新聞的事件，情緒預警本來就不可能提前示警。",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="情緒異常預警歷史回測（依預先聲明執行）")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("events", help="列出依規則選出的事件與預估請求數")
    run_parser = sub.add_parser("run", help="回補、評分、判斷並產出報告")
    run_parser.add_argument("--llm-model", default=ALERT_LLM_MODEL)
    run_parser.add_argument("--only", nargs="+", metavar="TICKER", help="試跑指定股票（報告另存 trial 檔）")
    args = parser.parse_args()

    rets, market, sessions = load_prices()
    events = select_events(rets, market, sessions) + NARRATIVE
    if args.cmd == "events":
        cmd_events(events, rets, market, sessions)
        return

    out_path = DOCS_DIR / "alert_backtest.md"
    if args.only:
        events = [e for e in events if e.ticker in args.only]
        out_path = DOCS_DIR / "alert_backtest_trial.md"
    cmd_run(events, rets, market, sessions, args.llm_model, out_path)


if __name__ == "__main__":
    main()
