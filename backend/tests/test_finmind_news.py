from datetime import datetime, timezone

from newssent.data.finmind_news import parse_rows


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
