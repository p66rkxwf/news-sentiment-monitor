from datetime import date, datetime, time, timedelta, timezone

import pytest

from newssent.data.finmind_news import FINMIND_PROVIDER
from newssent.data.provider import Article
from newssent.data.score_store import ScoreStore
from newssent.inference.alert_board import assess_ticker, build_board
from newssent.inference.alert_recorder import record
from newssent.inference.alerts import AlertLevel, session_open
from tests.alert_helpers import CALM_DAYS, fill, weekdays

UTC = timezone.utc
SCORER = "fake-1"
SESSIONS = weekdays(date(2025, 3, 3), 24)


@pytest.fixture
def store(tmp_path):
    s = ScoreStore(tmp_path / "alerts.db")
    yield s
    s.close()


def _utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)


def _quiet(_: str) -> None:
    pass


# --- 分數庫 ---


def test_syndicated_copy_keeps_earliest_time_and_its_source(store):
    store.upsert_headlines(
        "2330.TW", [Article("台積電地震損失", "u-late", "2025-01-23T05:00:00+00:00", "Yahoo股市")], origin="backfill"
    )
    store.upsert_headlines(
        "2330.TW", [Article("台積電地震損失", "u-early", "2025-01-23T10:00:00+08:00", "鉅亨")], origin="backfill"
    )
    store.save_scores("2330.TW", SCORER, [("台積電地震損失", 1.0, 0.0, 0.0)])
    [headline] = store.scored_headlines("2330.TW", SCORER, _utc(2025, 1, 23), _utc(2025, 1, 24))
    assert headline.published_at == _utc(2025, 1, 23, 2, 0)
    assert (headline.source, headline.url) == ("鉅亨", "u-early")


def test_naive_publish_time_is_rejected(store):
    with pytest.raises(ValueError):
        store.upsert_headlines("2330.TW", [Article("t", "", "2025-01-23T05:00:00", "s")], origin="backfill")


def test_scored_headlines_window_is_half_open(store):
    articles = [
        Article("在起點", "", "2025-01-23T00:00:00+00:00", "s"),
        Article("在終點", "", "2025-01-24T00:00:00+00:00", "s"),
    ]
    store.upsert_headlines("2330.TW", articles, origin="backfill")
    store.save_scores("2330.TW", SCORER, [("在起點", 0, 1, 0), ("在終點", 0, 1, 0)])
    rows = store.scored_headlines("2330.TW", SCORER, _utc(2025, 1, 23), _utc(2025, 1, 24))
    assert [h.title for h in rows] == ["在起點"]


# --- 記錄器 ---


class FakeClient:
    def __init__(self, titles: list[str] | None = None):
        self.calls: list[date] = []
        self.titles = titles

    def fetch_day(self, stock_id: str, utc_day: date) -> list[Article]:
        self.calls.append(utc_day)
        published = datetime.combine(utc_day, time(3), tzinfo=UTC).isoformat()
        titles = self.titles or [f"{stock_id} {utc_day} 標題"]
        return [Article(title, "", published, "測試社") for title in titles]


class FlakyScorer:
    """第一次呼叫時讓指定標題評分失敗，模擬 LLM 逾時；並記下看過哪些標題。"""

    version = SCORER

    def __init__(self, fail_title: str | None = None):
        self.fail_title = fail_title
        self.calls = 0
        self.seen: list[str] = []

    def score(self, target: str, titles: list[str]):
        self.calls += 1
        self.seen += titles
        return [None if self.calls == 1 and t == self.fail_title else (0.0, 1.0, 0.0) for t in titles]


def test_recorder_is_idempotent_and_refetches_unfinished_today(store):
    client, scorer = FakeClient(), FlakyScorer(fail_title="2330 2025-01-21 標題")
    now = _utc(2025, 1, 22, 12)

    def run():
        record(store, client, scorer, {"2330.TW": "台積電"}, date(2025, 1, 20), date(2025, 1, 22), now=now, log=_quiet)

    run()
    assert client.calls == [date(2025, 1, 20), date(2025, 1, 21), date(2025, 1, 22)]
    assert store.fetched_days("2330.TW", FINMIND_PROVIDER) == {date(2025, 1, 20), date(2025, 1, 21)}
    assert store.unscored("2330.TW", SCORER) == ["2330 2025-01-21 標題"]

    client.calls.clear()
    run()
    assert client.calls == [date(2025, 1, 22)]  # 只重抓尚未結束的今天
    assert store.unscored("2330.TW", SCORER) == []  # 上次評分失敗的補上


def test_origin_distinguishes_live_from_backfill(store):
    client, scorer = FakeClient(), FlakyScorer()
    now = _utc(2025, 3, 1, 12)
    for day in (date(2025, 1, 2), date(2025, 2, 28)):
        record(store, client, scorer, {"2330.TW": "台積電"}, day, day, now=now, log=_quiet)
    rows = store.scored_headlines("2330.TW", SCORER, _utc(2025, 1, 1), _utc(2025, 3, 2))
    assert [(h.published_at.date(), h.origin) for h in rows] == [
        (date(2025, 1, 2), "backfill"),
        (date(2025, 2, 28), "live"),
    ]


def test_price_reports_are_stored_but_not_sent_to_the_scorer(store):
    client = FakeClient(titles=["台積電跌40元至2410", "台積電8月營收創新高"])
    scorer = FlakyScorer()
    record(store, client, scorer, {"2330.TW": "台積電"}, date(2025, 1, 20), date(2025, 1, 20), now=_utc(2025, 3, 1), log=_quiet)
    assert scorer.seen == ["台積電8月營收創新高"]
    assert store.unscored("2330.TW", SCORER) == ["台積電跌40元至2410"]  # 原始標題仍保留在庫裡


# --- 看板 ---


def test_board_ranks_by_severity_and_attaches_negative_evidence(store):
    fill(store, "2330.TW", SESSIONS, ["negative"] * 3, SCORER)                            # z ≈ −6.8
    fill(store, "2382.TW", SESSIONS, ["negative", "negative", "positive"] + ["neutral"] * 5, SCORER)  # z ≈ −1.7
    fill(store, "2317.TW", SESSIONS, CALM_DAYS[0], SCORER)                                # z ≈ +1.0
    universe = {"2317.TW": "鴻海", "2330.TW": "台積電", "2382.TW": "廣達"}

    board = build_board(store, universe, SCORER, SESSIONS, SESSIONS[-1], today_utc=date(2026, 1, 1))

    assert [(a.ticker, a.assessment.level) for a in board] == [
        ("2330.TW", AlertLevel.HIGH),
        ("2382.TW", AlertLevel.WATCH),
        ("2317.TW", AlertLevel.NORMAL),
    ]
    assert len(board[0].evidence) == 3
    assert all(e.score < 0 for e in board[0].evidence)
    assert len(board[1].evidence) == 2
    assert board[2].evidence == []


def test_already_scored_price_reports_do_not_count(store):
    # 若盤勢報導照算，當日 3 平靜＋3 負面 → z ≈ −2.9（high）；排除後只剩平靜的 3 則
    fill(store, "2330.TW", SESSIONS, CALM_DAYS[0], SCORER)
    published = (session_open(SESSIONS[-1]) - timedelta(hours=1)).isoformat()
    reports = [Article(f"台積電跌{n}0元", "", published, "測試社") for n in (1, 2, 3)]
    store.upsert_headlines("2330.TW", reports, origin="backfill")
    store.save_scores("2330.TW", SCORER, [(a.title, 1.0, 0.0, 0.0) for a in reports])

    alert = assess_ticker(store, "2330.TW", "台積電", SCORER, SESSIONS, SESSIONS[-1], today_utc=date(2026, 1, 1))

    assert alert.assessment.level is AlertLevel.NORMAL
    assert alert.assessment.n == 3
    assert alert.evidence == []


def test_unfetched_days_are_insufficient_not_calm(store):
    fill(store, "2330.TW", SESSIONS, ["negative"] * 3, SCORER, unfetched={SESSIONS[10]})
    alert = assess_ticker(store, "2330.TW", "台積電", SCORER, SESSIONS, SESSIONS[-1], today_utc=date(2026, 1, 1))
    assert alert.assessment.level is AlertLevel.INSUFFICIENT
    assert "尚未抓齊" in alert.assessment.reason


def test_todays_unfinished_utc_day_is_not_required(store):
    fill(store, "2330.TW", SESSIONS, ["negative"] * 3, SCORER, unfetched={SESSIONS[-1]})
    alert = assess_ticker(store, "2330.TW", "台積電", SCORER, SESSIONS, SESSIONS[-1], today_utc=SESSIONS[-1])
    assert alert.assessment.level is AlertLevel.HIGH
