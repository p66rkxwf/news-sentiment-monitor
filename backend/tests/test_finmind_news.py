from datetime import date, datetime, timezone

import httpx
import pytest

from newssent.data.finmind_news import FinMindError, FinMindNewsClient, parse_rows


def _row(when: str, title: str, source: str = "Yahoo奇摩股市", link: str = "https://example.com") -> dict:
    return {"date": when, "stock_id": "2382", "title": title, "source": source, "link": link, "description": ""}


def test_naive_finmind_time_is_parsed_as_utc():
    # 實測證據：「廣達一度觸跌停」標在 01:38，只有 UTC（台北 09:38、已開盤）說得通
    [article] = parse_rows([_row("2025-02-03 01:38:08", "廣達一度觸跌停 - Yahoo奇摩股市")])
    assert datetime.fromisoformat(article.published_at) == datetime(2025, 2, 3, 1, 38, 8, tzinfo=timezone.utc)


def test_forum_posts_are_dropped():
    post = _row(
        "2025-01-23 00:24:51",
        "2330 台積電 - 抱股過年「黃仁勳概念股」最搶手！｜股市爆料同學會 - CMoney",
        source="CMoney",
    )
    assert parse_rows([post]) == []


def test_syndicated_copies_collapse_to_earliest_with_source_suffix_removed():
    rows = [
        _row("2025-01-28 03:03:18", "最後買進時機？台積電獲川普「大訂單」 - Yahoo奇摩股市",
             source="Yahoo奇摩股市", link="https://yahoo"),
        _row("2025-01-28 02:44:00", "最後買進時機？台積電獲川普「大訂單」 - FTNN新聞網",
             source="FTNN新聞網", link="https://ftnn"),
    ]
    [article] = parse_rows(rows)
    assert article.title == "最後買進時機？台積電獲川普「大訂單」"
    assert (article.source, article.url) == ("FTNN新聞網", "https://ftnn")
    assert article.published_at.startswith("2025-01-28T02:44:00")


def test_rows_missing_title_or_date_are_skipped():
    assert parse_rows([_row("", "有標題沒時間"), _row("2025-01-28 02:44:00", "")]) == []


def test_output_is_sorted_by_publish_time():
    rows = [_row("2025-01-28 09:00:00", "晚"), _row("2025-01-28 01:00:00", "早")]
    assert [a.title for a in parse_rows(rows)] == ["早", "晚"]


# --- 暫時性錯誤重試：一次網路逾時不該讓幾小時的回補整個停掉（2026-09-26 實際發生過） ---

DAY = date(2026, 9, 1)
REQUEST = httpx.Request("GET", "https://api.finmindtrade.com/api/v4/data")


def _ok():
    return httpx.Response(200, json={"status": 200, "data": [_row("2026-09-01 01:00:00", "台積電法說會")]}, request=REQUEST)


def _client(responses, sleeps):
    """依序回傳 responses（例外就丟出）的假 http_get；sleeps 記錄退避等待的秒數。"""
    queue = list(responses)
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs.get("params"))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    client = FinMindNewsClient(min_interval=0, backoff=30.0, retries=3, http_get=fake_get, sleep=sleeps.append)
    return client, calls


def test_transient_timeout_is_retried_with_backoff():
    sleeps = []
    client, calls = _client([httpx.ReadTimeout("timed out"), httpx.ConnectError("reset"), _ok()], sleeps)
    [article] = client.fetch_day("2330", DAY)
    assert article.title == "台積電法說會"
    assert len(calls) == 3
    assert sleeps == [30.0, 60.0]


def test_server_errors_are_retried_too():
    sleeps = []
    client, calls = _client([httpx.Response(503, request=REQUEST), _ok()], sleeps)
    assert len(client.fetch_day("2330", DAY)) == 1
    assert len(calls) == 2


def test_persistent_network_failure_becomes_finmind_error():
    # 轉成 FinMindError，recorder 才會印「已存檔、重跑即可接續」而不是整段 traceback
    sleeps = []
    client, calls = _client([httpx.ReadTimeout("timed out")] * 4, sleeps)
    with pytest.raises(FinMindError, match="ReadTimeout"):
        client.fetch_day("2330", DAY)
    assert len(calls) == 4
    assert sleeps == [30.0, 60.0, 120.0]


def test_quota_exhausted_is_not_retried():
    # 額度用盡要等一小時，重試幾分鐘沒有用：立即停下，交給使用者稍後重跑
    sleeps = []
    quota = httpx.Response(402, json={"status": 402, "msg": "Requests reach the upper limit."}, request=REQUEST)
    client, calls = _client([quota], sleeps)
    with pytest.raises(FinMindError, match="upper limit"):
        client.fetch_day("2330", DAY)
    assert len(calls) == 1
    assert sleeps == []
