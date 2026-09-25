"""GET /api/alerts：某交易日全池的情緒異常預警（預設只列 high / watch）；
GET /api/alerts/sessions：可查詢的交易日清單（前端切換日期用，避免猜到非交易日而收到 422）。"""

from collections import Counter
from dataclasses import asdict
from datetime import date, datetime, timezone

from fastapi import APIRouter, Query, Request

from newssent.api.errors import AlertDataUnavailableError, InvalidSessionError
from newssent.api.schemas import (
    AlertEvidence,
    AlertSessionsResponse,
    AlertsResponse,
    AlertSummary,
    DailySentimentPoint,
    StockAlert,
)
from newssent.config import ALERT_SCORER, ALERT_UNIVERSE
from newssent.data.score_store import ScoreStore
from newssent.inference.alert_board import TickerAlert, build_board
from newssent.inference.alerts import AlertLevel, AlertParams, extend_sessions, session_open

router = APIRouter(prefix="/api", tags=["alerts"])

TRIGGERED = (AlertLevel.HIGH, AlertLevel.WATCH)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def _to_item(alert: TickerAlert) -> StockAlert:
    a = alert.assessment
    return StockAlert(
        ticker=alert.ticker,
        name=alert.name,
        level=a.level.value,
        reason=a.reason,
        z_score=_round(a.z),
        score_today=_round(a.score),
        baseline_mean=_round(a.baseline_mean),
        baseline_std=_round(a.baseline_std),
        score_change=_round(a.change),
        article_count=a.n,
        baseline_days=a.baseline_days,
        recent_score=_round(a.recent_score),
        recent=[
            DailySentimentPoint(session=d.session, score=_round(d.score), article_count=d.n)
            for d in a.recent
        ],
        evidence=[
            AlertEvidence(
                title=e.title, source=e.source, published_at=e.published_at.isoformat(), score=_round(e.score)
            )
            for e in alert.evidence
        ],
    )


def _calendar(store: ScoreStore, now: datetime) -> list[date]:
    """已確認交易日＋推估到下一個尚未開盤的交易日；分數庫沒有交易日就無從判斷（503）。"""
    confirmed = store.sessions()
    if not confirmed:
        raise AlertDataUnavailableError()
    return extend_sessions(confirmed, now)


@router.get("/alerts/sessions", response_model=AlertSessionsResponse)
def get_alert_sessions(request: Request) -> AlertSessionsResponse:
    sessions = _calendar(request.app.state.score_store, datetime.now(timezone.utc))
    return AlertSessionsResponse(sessions=sessions, latest=sessions[-1])


@router.get("/alerts", response_model=AlertsResponse)
def get_alerts(
    request: Request,
    as_of: date | None = Query(
        None, description="交易日 YYYY-MM-DD；省略＝最近一個交易日（可能尚未開盤、標題仍在累積）"
    ),
    include_all: bool = Query(False, description="true 時連 normal / insufficient 也列出"),
) -> AlertsResponse:
    store: ScoreStore = request.app.state.score_store
    now = datetime.now(timezone.utc)
    sessions = _calendar(store, now)
    if as_of is None:
        as_of = sessions[-1]
    elif as_of not in sessions:
        raise InvalidSessionError(as_of.isoformat())

    params = AlertParams()
    board = build_board(store, ALERT_UNIVERSE, ALERT_SCORER, sessions, as_of, params, today_utc=now.date())
    counts = Counter(alert.assessment.level for alert in board)
    shown = board if include_all else [a for a in board if a.assessment.level in TRIGGERED]
    return AlertsResponse(
        as_of=as_of,
        window_closed=now >= session_open(as_of),
        scorer=ALERT_SCORER,
        params=asdict(params),
        universe_size=len(board),
        summary=AlertSummary(**{level.value: counts.get(level, 0) for level in AlertLevel}),
        alerts=[_to_item(a) for a in shown],
    )
