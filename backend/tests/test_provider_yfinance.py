"""YFinanceNewsProvider 單元測試：雙 payload 解析、快取命中、stale 降級。

全部離線（monkeypatch _fetch），不打真實網路。
"""

import pytest

from newssent.data.cache import NewsCache
from newssent.data.provider import (
    Article,
    NewsProviderError,
    YFinanceNewsProvider,
    _to_article,
)


def test_to_article_new_format():
    item = {
        "id": "abc",
        "content": {
            "title": "Apple hits record high",
            "pubDate": "2026-07-10T12:00:00Z",
            "canonicalUrl": {"url": "https://example.com/a"},
            "clickThroughUrl": {"url": "https://example.com/b"},
            "provider": {"displayName": "Reuters"},
        },
    }
    art = _to_article(item)
    assert art == Article(
        title="Apple hits record high",
        url="https://example.com/a",  # canonicalUrl 優先
        published_at="2026-07-10T12:00:00Z",
        source="Reuters",
    )


def test_to_article_new_format_falls_back_to_clickthrough_url():
    item = {"content": {"title": "T", "clickThroughUrl": {"url": "https://example.com/c"}}}
    art = _to_article(item)
    assert art is not None and art.url == "https://example.com/c"


def test_to_article_old_format_epoch_converted():
    item = {
        "title": "Old style news",
        "link": "https://example.com/old",
        "publisher": "Bloomberg",
        "providerPublishTime": 1752192000,  # 2025-07-11T00:00:00Z
    }
    art = _to_article(item)
    assert art is not None
    assert art.published_at.startswith("2025-07-1")
    assert art.published_at.endswith("+00:00")
    assert art.source == "Bloomberg"


def test_to_article_filters_garbage():
    assert _to_article({"content": {"title": "  "}}) is None  # 空標題
    assert _to_article({"title": ""}) is None
    assert _to_article("not a dict") is None


@pytest.fixture
def cache(tmp_path):
    c = NewsCache(tmp_path / "news.db")
    yield c
    c.close()


def _articles(n: int = 2) -> list[Article]:
    return [
        Article(title=f"t{i}", url=f"https://x/{i}", published_at="2026-07-11T00:00:00Z", source="s")
        for i in range(n)
    ]


def test_cache_hit_skips_fetch(cache, monkeypatch):
    provider = YFinanceNewsProvider(cache=cache, bucket_seconds=3600)
    calls = {"n": 0}

    def fake_fetch(ticker, limit):
        calls["n"] += 1
        return _articles()

    monkeypatch.setattr(provider, "_fetch", fake_fetch)

    r1 = provider.get_news("AAPL", limit=5)
    r2 = provider.get_news("AAPL", limit=5)  # 同一時間桶：走快取
    assert calls["n"] == 1
    assert not r1.stale and not r2.stale
    assert [a.title for a in r2.articles] == ["t0", "t1"]


def test_fetch_failure_falls_back_to_stale_cache(cache, monkeypatch):
    provider = YFinanceNewsProvider(cache=cache, bucket_seconds=3600)
    # 先塞一筆「舊時間桶」的快取
    cache.write("AAPL", bucket=1, articles=[a.to_dict() for a in _articles(1)])

    monkeypatch.setattr(
        provider, "_fetch", lambda t, n: (_ for _ in ()).throw(ConnectionError("斷網"))
    )
    result = provider.get_news("AAPL", limit=5)
    assert result.stale is True
    assert result.articles[0].title == "t0"


def test_fetch_failure_without_cache_raises(cache, monkeypatch):
    provider = YFinanceNewsProvider(cache=cache, bucket_seconds=3600)
    monkeypatch.setattr(
        provider, "_fetch", lambda t, n: (_ for _ in ()).throw(ConnectionError("斷網"))
    )
    with pytest.raises(NewsProviderError):
        provider.get_news("TSLA", limit=5)


def test_empty_yfinance_response_treated_as_failure(cache, monkeypatch):
    """yfinance 回空清單視為失敗（觸發降級），不寫入空快取。"""

    class FakeTicker:
        def __init__(self, ticker):
            pass

        def get_news(self, count):
            return []

    provider = YFinanceNewsProvider(cache=cache, bucket_seconds=3600)
    monkeypatch.setattr("yfinance.Ticker", FakeTicker)
    with pytest.raises(NewsProviderError):
        provider.get_news("MSFT", limit=5)
