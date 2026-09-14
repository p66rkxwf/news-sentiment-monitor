"""某個交易日的全池情緒預警看板：分數庫 → 每日分數 → 規則判斷 → 附上觸發標題。

API（GET /api/alerts）與回測工具（tools/alert_backtest.py）走同一條路徑——
demo 畫面上看到的歷史警示，與回測報告算出來的，保證是同一套計算。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

from newssent.data.finmind_news import FINMIND_PROVIDER
from newssent.data.score_store import ScoreStore, utc_days
from newssent.inference.alerts import (
    AlertLevel,
    AlertParams,
    Assessment,
    DailyScore,
    assess,
    daily_scores,
    headline_score,
    is_price_report,
    session_open,
)

EVIDENCE_LIMIT = 3
LEVEL_ORDER = {AlertLevel.HIGH: 0, AlertLevel.WATCH: 1, AlertLevel.NORMAL: 2, AlertLevel.INSUFFICIENT: 3}


@dataclass(frozen=True)
class Evidence:
    title: str
    source: str
    published_at: datetime
    score: float


@dataclass(frozen=True)
class TickerAlert:
    ticker: str
    name: str
    assessment: Assessment
    evidence: list[Evidence]  # 當日最負面的標題，供人工覆核「警示是不是被一則誤判觸發的」


def assess_ticker(
    store: ScoreStore,
    ticker: str,
    name: str,
    scorer: str,
    sessions: Sequence[date],
    as_of: date,
    params: AlertParams = AlertParams(),
    today_utc: date | None = None,
) -> TickerAlert:
    """sessions 須為遞增的交易日曆且包含 as_of。"""
    today_utc = today_utc or datetime.now(timezone.utc).date()
    idx = list(sessions).index(as_of)
    span = list(sessions[max(0, idx - params.baseline_sessions - 1): idx + 1])
    # 讀取時才過濾盤勢報導（而非只在評分時）：規則調整前就評過分的標題也一致排除
    rows = [
        r
        for r in store.scored_headlines(ticker, scorer, session_open(span[0]), session_open(as_of))
        if not is_price_report(r.title)
    ]
    series = daily_scores(
        ((r.published_at, headline_score(r.p_negative, r.p_positive)) for r in rows), span
    ) or [DailyScore(as_of, None, 0)]
    assessment = assess(series, params)

    # 沒抓過的日子讀起來和「當天沒新聞」一模一樣，不先排除就會把缺資料誤判成情緒平穩
    done = store.fetched_days(ticker, FINMIND_PROVIDER)
    missing = [d for d in utc_days(span[0], min(as_of, today_utc - timedelta(days=1))) if d not in done]
    if missing:
        assessment = replace(
            assessment,
            level=AlertLevel.INSUFFICIENT,
            z=None,
            reason=f"新聞尚未抓齊：缺 {len(missing)} 個 UTC 日（請先執行 alert_recorder）",
        )

    evidence: list[Evidence] = []
    if len(span) >= 2:
        opened = session_open(span[-2])
        todays = sorted(
            (
                Evidence(r.title, r.source, r.published_at, headline_score(r.p_negative, r.p_positive))
                for r in rows
                if r.published_at >= opened
            ),
            key=lambda e: e.score,
        )
        evidence = [e for e in todays if e.score < 0][:EVIDENCE_LIMIT]
    return TickerAlert(ticker=ticker, name=name, assessment=assessment, evidence=evidence)


def build_board(
    store: ScoreStore,
    universe: dict[str, str],
    scorer: str,
    sessions: Sequence[date],
    as_of: date,
    params: AlertParams = AlertParams(),
    today_utc: date | None = None,
) -> list[TickerAlert]:
    """全池判斷，依嚴重度排序：high → watch → normal → insufficient，同級內 z 越低越前面。"""
    board = [
        assess_ticker(store, ticker, name, scorer, sessions, as_of, params, today_utc)
        for ticker, name in universe.items()
    ]
    return sorted(
        board,
        key=lambda a: (
            LEVEL_ORDER[a.assessment.level],
            a.assessment.z if a.assessment.z is not None else 0.0,
            a.ticker,
        ),
    )
