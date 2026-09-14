"""情緒預警資料記錄器：抓台股中文新聞 → 入庫 → 評分。每日排程與歷史回補走同一條路徑。

冪等、可中斷續跑：已完整抓過的 (ticker, UTC 日) 記在 fetch_log 不重抓；已評分的標題不重評；
FinMind 額度用盡或 LLM 中途失敗，重跑同一指令即從斷點接續。
盤勢報導標題照常入庫（保留原始資料），但不送評分——省下約三成的 LLM 時間。

用法（backend/ 目錄執行）:
    # 每日排程：全池、最近 45 天（前 20 個交易日的基準約需 30 個日曆天）
    python -m newssent.inference.alert_recorder
    # 歷史回補：新聞起日要比「想評估的第一個交易日」再往前推至少 35 天
    python -m newssent.inference.alert_recorder --tickers 2382.TW 6669.TW --start 2024-12-15 --end 2025-02-05
"""

from __future__ import annotations

import argparse
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol

from newssent.config import ALERT_LLM_MODEL, ALERT_SCORE_DB_PATH, ALERT_UNIVERSE, FINMIND_TOKEN
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


def fetch_twse_sessions(start: date, end: date) -> list[date]:
    """加權指數實際有成交的日子＝台股交易日。"""
    import yfinance as yf

    hist = yf.Ticker("^TWII").history(
        start=start.isoformat(), end=(end + timedelta(days=1)).isoformat(), auto_adjust=False
    )
    return sorted({ts.date() for ts in hist.index})


def record(
    store: ScoreStore,
    client: DailyNewsClient,
    scorer: HeadlineScorer,
    tickers: dict[str, str],
    start: date,
    end: date,
    now: datetime | None = None,
    log: Callable[[str], None] = print,
) -> None:
    now = now or datetime.now(timezone.utc)
    today = now.date()
    for ticker, name in tickers.items():
        stock_id = ticker.split(".")[0]
        done = store.fetched_days(ticker, FINMIND_PROVIDER)
        fetched = 0
        for day in utc_days(start, min(end, today)):
            if day in done:
                continue
            articles = client.fetch_day(stock_id, day)
            day_end = datetime.combine(day + timedelta(days=1), time(), tzinfo=timezone.utc)
            store.upsert_headlines(ticker, articles, origin="live" if now - day_end <= LIVE_LAG else "backfill")
            if day < today:  # 今天還沒結束，不記為抓完，下次會重抓補齊
                store.mark_fetched(ticker, day, FINMIND_PROVIDER, len(articles))
            fetched += len(articles)

        pending = store.unscored(ticker, scorer.version)
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
            f"{ticker} {name}：新抓 {fetched} 則、評分 {len(to_score) - failed} 則"
            + (f"、略過盤勢報導 {skipped} 則" if skipped else "")
            + (f"、{failed} 則評分失敗（下次重試）" if failed else "")
        )


def main(argv: list[str] | None = None) -> None:
    from newssent.data.finmind_news import FinMindError, FinMindNewsClient
    from newssent.inference.llm_review import OllamaReviewer
    from newssent.inference.scorers import LlmScorer

    parser = argparse.ArgumentParser(description="抓台股中文新聞並評分，供情緒異常預警使用")
    parser.add_argument("--tickers", nargs="+", metavar="TICKER", help="例：2330.TW；省略＝全池")
    parser.add_argument("--start", type=date.fromisoformat, help="新聞起日（UTC 日）")
    parser.add_argument("--end", type=date.fromisoformat, help="新聞迄日（UTC 日），預設今天")
    parser.add_argument("--llm-model", default=ALERT_LLM_MODEL)
    args = parser.parse_args(argv)

    unknown = sorted(set(args.tickers or []) - ALERT_UNIVERSE.keys())
    if unknown:
        parser.error(f"不在預警股票池內：{', '.join(unknown)}")
    tickers = {t: ALERT_UNIVERSE[t] for t in args.tickers} if args.tickers else dict(ALERT_UNIVERSE)
    end = args.end or datetime.now(timezone.utc).date()
    start = args.start or end - timedelta(days=DEFAULT_LOOKBACK_DAYS)
    if start > end:
        parser.error("--start 不可晚於 --end")

    reviewer = OllamaReviewer(model=args.llm_model)
    if not reviewer.available():
        parser.error(f"本機 Ollama 沒有模型 {args.llm_model}（或 Ollama 未啟動）")

    store = ScoreStore(ALERT_SCORE_DB_PATH)
    try:
        store.save_sessions(fetch_twse_sessions(start - timedelta(days=10), end))
        record(store, FinMindNewsClient(token=FINMIND_TOKEN), LlmScorer(reviewer), tickers, start, end)
    except FinMindError as exc:
        raise SystemExit(f"{exc}\n已完成的進度都已存檔，額度恢復後重跑同一指令即可接續。") from exc
    finally:
        store.close()


if __name__ == "__main__":
    main()
