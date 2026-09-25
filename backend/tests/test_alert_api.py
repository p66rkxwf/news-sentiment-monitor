from datetime import date, timedelta

import pytest

from newssent.config import ALERT_SCORER, ALERT_UNIVERSE
from newssent.data.score_store import ScoreStore
from tests.alert_helpers import CALM_DAYS, fill, weekdays

SESSIONS = weekdays(date(2025, 3, 3), 24)
AS_OF = SESSIONS[-1].isoformat()


def _client_with_store(store: ScoreStore):
    from fastapi.testclient import TestClient

    from newssent.api.main import app

    with TestClient(app) as client:
        app.state.limiter.enabled = False
        app.state.analyzer = None
        # 覆蓋 lifespan 開的真實分數庫，改用測試專用的暫存庫
        app.state.score_store = store
        yield client


@pytest.fixture
def alert_client(tmp_path):
    store = ScoreStore(tmp_path / "alerts.db")
    fill(store, "2330.TW", SESSIONS, ["negative"] * 3, ALERT_SCORER)
    fill(store, "2317.TW", SESSIONS, CALM_DAYS[0], ALERT_SCORER)
    yield from _client_with_store(store)
    store.close()


@pytest.fixture
def empty_alert_client(tmp_path):
    store = ScoreStore(tmp_path / "empty.db")
    yield from _client_with_store(store)
    store.close()


def test_alerts_lists_only_triggered_stocks_by_default(alert_client):
    r = alert_client.get(f"/api/alerts?as_of={AS_OF}")
    assert r.status_code == 200
    body = r.json()
    assert [a["ticker"] for a in body["alerts"]] == ["2330.TW"]
    top = body["alerts"][0]
    assert top["level"] == "high"
    assert top["score_today"] == -1.0
    assert top["z_score"] < -2
    assert top["score_change"] < 0
    assert len(top["recent"]) == 5
    assert len(top["evidence"]) == 3
    assert body["summary"] == {"high": 1, "watch": 0, "normal": 1, "insufficient": len(ALERT_UNIVERSE) - 2}
    assert body["universe_size"] == len(ALERT_UNIVERSE)
    assert body["window_closed"] is True
    assert body["scorer"] == ALERT_SCORER


def test_include_all_lists_insufficient_with_reason(alert_client):
    body = alert_client.get(f"/api/alerts?as_of={AS_OF}&include_all=true").json()
    assert len(body["alerts"]) == len(ALERT_UNIVERSE)
    assert body["alerts"][0]["ticker"] == "2330.TW"
    insufficient = [a for a in body["alerts"] if a["level"] == "insufficient"]
    assert insufficient
    assert all(a["reason"] for a in insufficient)


def test_non_trading_day_returns_422(alert_client):
    saturday = SESSIONS[0] - timedelta(days=2)
    r = alert_client.get(f"/api/alerts?as_of={saturday.isoformat()}")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_SESSION"


def test_empty_store_returns_503(empty_alert_client):
    r = empty_alert_client.get("/api/alerts")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ALERT_DATA_UNAVAILABLE"


def test_sessions_cover_confirmed_days_and_default_as_of(alert_client):
    r = alert_client.get("/api/alerts/sessions")
    assert r.status_code == 200
    body = r.json()
    sessions = [date.fromisoformat(s) for s in body["sessions"]]
    assert sessions == sorted(set(sessions))
    assert set(SESSIONS) <= set(sessions)
    assert all(s.weekday() < 5 for s in sessions)
    # 前端拿 latest 當預設日，必須和 /api/alerts 省略 as_of 時是同一天
    assert body["latest"] == body["sessions"][-1]
    assert alert_client.get("/api/alerts").json()["as_of"] == body["latest"]


def test_sessions_empty_store_returns_503(empty_alert_client):
    r = empty_alert_client.get("/api/alerts/sessions")
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "ALERT_DATA_UNAVAILABLE"
