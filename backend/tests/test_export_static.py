"""靜態站匯出：檔案結構與「寧可不部署也不發布錯的資料」的關卡。"""

import json
from datetime import date

import pytest

from newssent.config import ALERT_SCORER
from newssent.data.score_store import ScoreStore
from newssent.export_static import ExportError, run_export
from tests.alert_helpers import CALM_DAYS, fill, weekdays
from tests.conftest import FakeProvider

SESSIONS = weekdays(date(2025, 3, 3), 24)


@pytest.fixture
def alert_store(tmp_path):
    store = ScoreStore(tmp_path / "alerts.db")
    yield store
    store.close()


def _use_store(client, store):
    from newssent.api.main import app

    app.state.score_store = store  # 覆蓋 lifespan 開的真實分數庫
    return client


def _export(client, out, **kw):
    kw.setdefault("tickers", ["AAPL"])
    # API 的交易日曆會從 2025 年的合成資料一路推估到今天：放寬匯出範圍才涵蓋得到合成的那段
    kw.setdefault("session_limit", 10_000)
    return run_export(client, out, log=lambda *_: None, **kw)


def test_writes_site_layout_and_meta(client_with_model, alert_store, tmp_path):
    fill(alert_store, "2330.TW", SESSIONS, ["negative"] * 3, ALERT_SCORER)
    fill(alert_store, "2317.TW", SESSIONS, CALM_DAYS[0], ALERT_SCORER)
    client = _use_store(client_with_model, alert_store)
    out = tmp_path / "data"
    meta = _export(client, out, alerts_status="ok")

    for rel in ["model.json", "tickers.json", "stocks/AAPL/sentiment.json", "stocks/AAPL/news.json",
                "alerts/sessions.json", "meta.json"]:
        assert (out / rel).is_file(), rel

    calendar = json.loads((out / "alerts/sessions.json").read_text(encoding="utf-8"))
    assert calendar["latest"] == calendar["sessions"][-1]
    board = json.loads((out / f"alerts/{SESSIONS[-1].isoformat()}.json").read_text(encoding="utf-8"))
    assert board["opens_at"] == f"{SESSIONS[-1].isoformat()}T09:00:00+08:00"
    assert board["scorer"] == ALERT_SCORER
    assert len(board["alerts"]) == board["universe_size"]  # include_all：前端自行過濾 high/watch
    assert meta["alerts_latest"] == calendar["latest"]
    assert meta["alerts_status"] == "ok"
    assert json.loads((out / "tickers.json").read_text(encoding="utf-8"))["names"]["AAPL"] == "Apple"


def test_all_insufficient_boards_are_not_published(client_with_model, alert_store, tmp_path):
    # 換新評分器、還沒有任何分數：看板全是「資料不足」，不發布，但新聞與情緒照常
    alert_store.save_sessions(SESSIONS)
    out = tmp_path / "data"
    meta = _export(_use_store(client_with_model, alert_store), out)
    assert json.loads((out / "alerts/sessions.json").read_text(encoding="utf-8")) == {"sessions": [], "latest": None}
    assert meta["alerts_latest"] is None
    assert (out / "stocks/AAPL/sentiment.json").is_file()


def test_refuses_mock_model(client, tmp_path):
    with pytest.raises(ExportError, match="mock"):
        _export(client, tmp_path / "data")


def test_refuses_alert_calendar_going_backwards(client_with_model, alert_store, tmp_path):
    fill(alert_store, "2330.TW", SESSIONS, ["negative"] * 3, ALERT_SCORER)
    with pytest.raises(ExportError, match="倒退"):
        _export(_use_store(client_with_model, alert_store), tmp_path / "data",
                prev_meta={"alerts_latest": "2099-01-01"})


def test_refuses_low_ticker_coverage(client_with_model, tmp_path):
    from newssent.api.main import app

    app.state.news_provider = FakeProvider([])  # 新聞源全空 → 每檔 404
    with pytest.raises(ExportError, match="覆蓋率"):
        _export(client_with_model, tmp_path / "data")
