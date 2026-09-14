from datetime import date, datetime, timedelta, timezone

import pytest

from newssent.inference.alerts import (
    AlertLevel,
    AlertParams,
    DailyScore,
    assess,
    daily_scores,
    extend_sessions,
    headline_score,
    session_for,
)

TPE = timezone(timedelta(hours=8))

# 2025 春節：1/22 封關、2/3 開紅盤
CALENDAR = [date(2025, 1, 21), date(2025, 1, 22), date(2025, 2, 3), date(2025, 2, 4)]


def _series(baseline: list[float | None], today: float | None, today_n: int = 5) -> list[DailyScore]:
    start = date(2025, 1, 1)
    days = [
        DailyScore(start + timedelta(days=i), s, 0 if s is None else 5)
        for i, s in enumerate(baseline)
    ]
    days.append(DailyScore(start + timedelta(days=len(baseline)), today, today_n))
    return days


# 平均 0.2、樣本標準差 ≈ 0.1026 的基準期（交錯 0.1 / 0.3，共 20 天）
STEADY = [0.1, 0.3] * 10


def test_headline_score_is_positive_minus_negative():
    assert headline_score(p_negative=0.7, p_positive=0.1) == pytest.approx(-0.6)


# --- 資訊時點 ---


def test_headline_before_open_counts_for_same_session():
    at_0859 = datetime(2025, 1, 22, 8, 59, tzinfo=TPE)
    assert session_for(at_0859, CALENDAR) == date(2025, 1, 22)


def test_headline_at_or_after_open_counts_for_next_session():
    # 盤中才出現的消息不能拿來判斷當天——開盤那一刻起的標題歸下一個交易日
    assert session_for(datetime(2025, 1, 21, 9, 0, tzinfo=TPE), CALENDAR) == date(2025, 1, 22)
    assert session_for(datetime(2025, 1, 21, 13, 30, tzinfo=TPE), CALENDAR) == date(2025, 1, 22)


def test_headlines_during_market_closure_roll_to_reopening_session():
    during_lunar_new_year = datetime(2025, 1, 28, 20, 0, tzinfo=TPE)
    assert session_for(during_lunar_new_year, CALENDAR) == date(2025, 2, 3)


def test_utc_timestamp_is_converted_before_bucketing():
    # 01:38 UTC = 09:38 台北，已開盤 → 下一個交易日
    assert session_for(datetime(2025, 2, 3, 1, 38, tzinfo=timezone.utc), CALENDAR) == date(2025, 2, 4)


def test_headline_after_last_open_is_outside_calendar():
    assert session_for(datetime(2025, 2, 4, 10, 0, tzinfo=TPE), CALENDAR) is None


def test_naive_timestamp_is_rejected():
    with pytest.raises(ValueError):
        session_for(datetime(2025, 1, 22, 8, 0), CALENDAR)


def test_daily_scores_average_per_session_and_skip_left_boundary():
    scored = [
        (datetime(2025, 1, 20, 12, 0, tzinfo=TPE), -1.0),  # 早於第一個開盤：窗口外
        (datetime(2025, 1, 21, 10, 0, tzinfo=TPE), 0.5),   # → 1/22
        (datetime(2025, 1, 22, 8, 0, tzinfo=TPE), -0.5),   # → 1/22
        (datetime(2025, 1, 30, 8, 0, tzinfo=TPE), -1.0),   # 春節休市 → 2/3
    ]
    out = daily_scores(scored, CALENDAR)
    assert [d.session for d in out] == CALENDAR[1:]
    assert out[0] == DailyScore(date(2025, 1, 22), 0.0, 2)
    assert out[1] == DailyScore(date(2025, 2, 3), -1.0, 1)
    assert out[2] == DailyScore(date(2025, 2, 4), None, 0)


def test_extend_sessions_projects_until_an_unopened_session():
    friday = [date(2025, 1, 17)]
    saturday_noon = datetime(2025, 1, 18, 12, 0, tzinfo=TPE)
    assert extend_sessions(friday, saturday_noon) == [date(2025, 1, 17), date(2025, 1, 20)]
    monday_after_open = datetime(2025, 1, 20, 10, 0, tzinfo=TPE)
    assert extend_sessions(friday, monday_after_open)[-2:] == [date(2025, 1, 20), date(2025, 1, 21)]


def test_extend_sessions_leaves_future_calendar_alone():
    calendar = [date(2025, 1, 17), date(2025, 1, 20)]
    assert extend_sessions(calendar, datetime(2025, 1, 18, tzinfo=TPE)) == calendar


# --- 判斷規則 ---


def test_drop_beyond_two_sigma_is_high():
    a = assess(_series(STEADY, today=-0.1))  # z = (−0.1 − 0.2) / 0.1026 ≈ −2.9
    assert a.level is AlertLevel.HIGH
    assert a.z == pytest.approx(-2.92, abs=0.01)
    assert a.change == pytest.approx(-0.3)


def test_drop_between_thresholds_is_watch():
    a = assess(_series(STEADY, today=0.02))  # z ≈ −1.75
    assert a.level is AlertLevel.WATCH


def test_small_drop_is_normal():
    assert assess(_series(STEADY, today=0.1)).level is AlertLevel.NORMAL


def test_thresholds_are_strict():
    # 全用二進位可精確表示的數：平坦基準 0.5、σ 取下限 0.25、當日 0.125 → z 恰為 −1.5
    params = AlertParams(sigma_floor=0.25)
    a = assess(_series([0.5] * 20, today=0.125), params)
    assert a.z == -1.5
    assert a.level is AlertLevel.NORMAL  # 「低於 1.5σ」才觸發，剛好等於不算


def test_baseline_excludes_today():
    a = assess(_series(STEADY, today=-0.9))
    assert a.baseline_mean == pytest.approx(0.2)
    assert a.baseline_days == 20


def test_baseline_uses_only_the_last_20_sessions():
    a = assess(_series([-1.0] * 5 + STEADY, today=0.2))
    assert a.baseline_mean == pytest.approx(0.2)


def test_too_few_articles_today_is_insufficient_not_normal():
    a = assess(_series(STEADY, today=-0.9, today_n=1))
    assert a.level is AlertLevel.INSUFFICIENT
    assert a.z is None
    assert "當日標題" in a.reason


def test_sparse_baseline_is_insufficient():
    sparse = [0.2 if i % 3 == 0 else None for i in range(20)]  # 20 天只有 7 天有新聞
    a = assess(_series(sparse, today=-0.9))
    assert a.level is AlertLevel.INSUFFICIENT
    assert "基準期" in a.reason


def test_sigma_floor_prevents_blowup_on_flat_baseline():
    flat = [0.0] * 20  # 全中性：σ = 0
    mild = assess(_series(flat, today=-0.12))
    assert mild.baseline_std == 0.0
    assert mild.z == pytest.approx(-1.2)  # 以下限 0.10 計算，而非除以 0
    assert mild.level is AlertLevel.NORMAL
    assert assess(_series(flat, today=-0.25)).level is AlertLevel.HIGH


def test_recent_score_is_article_weighted():
    series = _series(STEADY, today=-1.0, today_n=10)
    series[-2] = DailyScore(series[-2].session, 1.0, 5)
    a = assess(series)
    recent = series[-5:]
    expected = sum(d.score * d.n for d in recent) / sum(d.n for d in recent)
    assert a.recent_score == pytest.approx(expected)
    assert len(a.recent) == 5
