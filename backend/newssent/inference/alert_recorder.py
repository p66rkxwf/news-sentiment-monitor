"""情緒預警資料記錄器：抓台股中文新聞 → 入庫 → 評分。每日排程與歷史回補走同一條路徑。

冪等、可中斷續跑：已完整抓過的 (ticker, UTC 日) 記在 fetch_log 不重抓；已評分的標題不重評；
FinMind 額度用盡或 LLM 中途失敗，重跑同一指令即從斷點接續。
盤勢報導標題照常入庫（保留原始資料），但不送評分——省下約三成的 LLM 時間。
先把全池新聞抓完再評分：評分額度（Gemini 每日上限）用盡時，新聞資料仍是完整的。

評分後端（--backend）：gemini＝雲端排程用的託管模型（預設，需 GEMINI_API_KEY）；
ollama＝本機 gemma3:27b（2026-09-26 以前的線上分數與回測都出自它）。兩者版本字串不同、分數分開存。

用法（backend/ 目錄執行）:
    # 每日排程：全池、最近 45 天（前 20 個交易日的基準約需 30 個日曆天）
    python -m newssent.inference.alert_recorder
    # 歷史回補：新聞起日要比「想評估的第一個交易日」再往前推至少 35 天
    python -m newssent.inference.alert_recorder --tickers 2382.TW 6669.TW --start 2024-12-15 --end 2025-02-05
    # 換評分器後回補分數（新聞已在庫內，只評分）：--score-since 限定評分範圍、--max-requests 控制額度
    python -m newssent.inference.alert_recorder --start 2026-07-15 --max-requests 6500

結束碼：0＝完成；1＝錯誤（FinMind 失敗、金鑰或模型設定錯誤）；3＝評分額度用盡（已評的都已存檔，下次接續）。
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol

from newssent.config import (
    ALERT_LLM_MODEL,
    ALERT_SCORE_DB_PATH,
    ALERT_SCORER,
    ALERT_UNIVERSE,
    FINMIND_TOKEN,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GEMINI_RPM,
    GEMINI_SYSTEM_INSTRUCTION,
)
from newssent.data.finmind_news import FINMIND_PROVIDER
from newssent.data.provider import Article
from newssent.data.score_store import ScoreStore, utc_days
from newssent.inference.alerts import is_price_report
from newssent.inference.scorers import HeadlineScorer

# 該 UTC 日結束後 48 小時內抓到的算 live，之後才抓的算 backfill（見 score_store 的 origin 說明）
LIVE_LAG = timedelta(hours=48)
SCORE_BATCH = 20
DEFAULT_LOOKBACK_DAYS = 45


class DailyNewsClient(Protocol):
    def fetch_day(self, stock_id: str, utc_day: date) -> list[Article]: ...


EXIT_QUOTA = 3


def fetch_twse_sessions(start: date, end: date, token: str = "") -> list[date]:
    """加權指數實際有成交的日子＝台股交易日。yfinance 失敗時改問 FinMind 的交易日表
    （雲端 IP 常被 Yahoo 限流；兩者都失敗才讓整次執行失敗）。"""
    try:
        import yfinance as yf

        hist = yf.Ticker("^TWII").history(
            start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), auto_adjust=False
        )
        sessions = sorted({ts.date() for ts in hist.index})
        if sessions:
            return sessions
    except Exception:
        pass
    from newssent.data.finmind_news import fetch_trading_dates

    return [d for d in fetch_trading_dates(start, end, token=token) if d <= end]


def record(
    store: ScoreStore,
    client: DailyNewsClient,
    scorer: HeadlineScorer,
    tickers: dict[str, str],
    start: date,
    end: date,
    now: datetime | None = None,
    log: Callable[[str], None] = print,
    score_since: date | None = None,
) -> None:
    """先抓全池新聞、再評分；score_since（預設＝start）以前發布的標題不評分。"""
    now = now or datetime.now(timezone.utc)
    today = now.date()
    fetched: dict[str, int] = {}
    for ticker in tickers:
        stock_id = ticker.split(".")[0]
        done = store.fetched_days(ticker, FINMIND_PROVIDER)
        fetched[ticker] = 0
        for day in utc_days(start, min(end, today)):
            if day in done:
                continue
            articles = client.fetch_day(stock_id, day)
            day_end = datetime.combine(day + timedelta(days=1), time(), tzinfo=timezone.utc)
            store.upsert_headlines(ticker, articles, origin="live" if now - day_end <= LIVE_LAG else "backfill")
            if day < today:  # 今天還沒結束，不記為抓完，下次會重抓補齊
                store.mark_fetched(ticker, day, FINMIND_PROVIDER, len(articles))
            fetched[ticker] += len(articles)

    for ticker, name in tickers.items():
        stock_id = ticker.split(".")[0]
        pending = store.unscored(ticker, scorer.version, since=score_since or start)
        to_score = [title for title in pending if not is_price_report(title)]
        target = f"{name}（{stock_id}）"
        failed = 0
        for i in range(0, len(to_score), SCORE_BATCH):
            batch = to_score[i: i + SCORE_BATCH]
            results = scorer.score(target, batch)
            ok = [(title, *proba) for title, proba in zip(batch, results) if proba is not None]
            failed += len(batch) - len(ok)
            store.save_scores(ticker, scorer.version, ok)
        skipped = len(pending) - len(to_score)
        log(
            f"{ticker} {name}：新抓 {fetched[ticker]} 則、評分 {len(to_score) - failed} 則"
            + (f"、略過盤勢報導 {skipped} 則" if skipped else "")
            + (f"、{failed} 則評分失敗（下次重試）" if failed else "")
        )


def _build_reviewer(args, parser):
    from newssent.inference.llm_review import GeminiReviewer, OllamaReviewer

    if args.backend == "ollama":
        reviewer = OllamaReviewer(model=args.llm_model or ALERT_LLM_MODEL)
        if not reviewer.available():
            parser.error(f"本機 Ollama 沒有模型 {reviewer.model}（或 Ollama 未啟動）")
        return reviewer
    if not GEMINI_API_KEY:
        parser.error("未設定 GEMINI_API_KEY（backend/.env 或環境變數）")
    reviewer = GeminiReviewer(
        model=args.llm_model or GEMINI_MODEL,
        api_key=GEMINI_API_KEY,
        rpm=GEMINI_RPM,
        max_requests=args.max_requests,
        system_instruction=GEMINI_SYSTEM_INSTRUCTION,
    )
    if not reviewer.available():
        parser.error(f"Gemini API 找不到模型 {reviewer.model}（或金鑰無效）")
    return reviewer


def main(argv: list[str] | None = None) -> int:
    from newssent.data.finmind_news import FinMindError, FinMindNewsClient
    from newssent.inference.llm_review import GeminiConfigError, GeminiQuotaExhausted
    from newssent.inference.scorers import LlmScorer

    parser = argparse.ArgumentParser(description="抓台股中文新聞並評分，供情緒異常預警使用")
    parser.add_argument("--tickers", nargs="+", metavar="TICKER", help="例：2330.TW；省略＝全池")
    parser.add_argument("--start", type=date.fromisoformat, help="新聞起日（UTC 日）")
    parser.add_argument("--end", type=date.fromisoformat, help="新聞迄日（UTC 日），預設今天")
    parser.add_argument("--backend", choices=("gemini", "ollama"), default="gemini", help="評分後端")
    parser.add_argument("--llm-model", help=f"預設 gemini={GEMINI_MODEL}、ollama={ALERT_LLM_MODEL}")
    parser.add_argument("--max-requests", type=int, help="本次最多呼叫幾次 Gemini（控制每日額度）")
    parser.add_argument("--score-since", type=date.fromisoformat, help="只評此 UTC 日（含）以後發布的標題，預設＝--start")
    args = parser.parse_args(argv)

    unknown = sorted(set(args.tickers or []) - ALERT_UNIVERSE.keys())
    if unknown:
        parser.error(f"不在預警股票池內：{', '.join(unknown)}")
    tickers = {t: ALERT_UNIVERSE[t] for t in args.tickers} if args.tickers else dict(ALERT_UNIVERSE)
    end = args.end or datetime.now(timezone.utc).date()
    start = args.start or end - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    if start > end:
        parser.error("--start 不可晚於 --end")

    scorer = LlmScorer(_build_reviewer(args, parser))
    if scorer.version != ALERT_SCORER:
        # 例如試用備援模型：可以跑，但 API 讀的是 ALERT_SCORER，這批分數不會出現在預警看板
        print(f"[注意] 評分器 {scorer.version} ≠ 線上評分器 {ALERT_SCORER}，結果不會顯示在預警看板")

    store = ScoreStore(ALERT_SCORE_DB_PATH)
    try:
        store.save_sessions(fetch_twse_sessions(start - timedelta(days=10), end, token=FINMIND_TOKEN))
        record(
            store, FinMindNewsClient(token=FINMIND_TOKEN), scorer, tickers, start, end,
            score_since=args.score_since,
        )
    except FinMindError as exc:
        print(f"{exc}\n已完成的進度都已存檔，額度恢復後重跑同一指令即可接續。")
        return 1
    except GeminiQuotaExhausted as exc:
        print(f"{exc}\n已評分的都已存檔，額度恢復後重跑即可接續。")
        return EXIT_QUOTA
    except GeminiConfigError as exc:
        print(str(exc))
        return 1
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
