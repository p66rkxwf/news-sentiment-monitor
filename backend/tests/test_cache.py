import pytest

from newssent.data.cache import InvalidTickerError, NewsCache, time_bucket, validate_ticker


def test_validate_ticker_accepts_valid():
    assert validate_ticker("AAPL") == "AAPL"
    assert validate_ticker("BRK.B") == "BRK.B"


@pytest.mark.parametrize("bad", ["../etc", "aapl", "TOOLONGX", "123", "", "AA;DROP"])
def test_validate_ticker_rejects_bad(bad):
    with pytest.raises(InvalidTickerError):
        validate_ticker(bad)


def test_time_bucket_groups_within_window():
    # 桶邊界固定在 bucket_seconds 的倍數；同一桶內的兩個時刻編號相同
    assert time_bucket(3600, now=3600) == time_bucket(3600, now=3600 + 3599)
    # 跨越下一個邊界則不同桶
    assert time_bucket(3600, now=3600) != time_bucket(3600, now=3600 + 3600)


def test_cache_roundtrip(tmp_path):
    cache = NewsCache(tmp_path / "c.db")
    articles = [{"title": "t", "url": "u", "published_at": "p", "source": "s"}]
    cache.write("AAPL", 100, articles)
    assert cache.read("AAPL", 100) == articles
    cache.close()


def test_cache_miss_returns_none(tmp_path):
    cache = NewsCache(tmp_path / "c.db")
    assert cache.read("AAPL", 100) is None
    cache.close()


def test_read_latest_ignores_bucket(tmp_path):
    cache = NewsCache(tmp_path / "c.db")
    cache.write("AAPL", 100, [{"title": "old", "url": "u", "published_at": "p", "source": "s"}])
    cache.write("AAPL", 200, [{"title": "new", "url": "u", "published_at": "p", "source": "s"}])
    latest = cache.read_latest("AAPL")
    assert latest[0]["title"] == "new"  # 取最大 bucket
    cache.close()


def test_cache_rejects_bad_ticker(tmp_path):
    cache = NewsCache(tmp_path / "c.db")
    with pytest.raises(InvalidTickerError):
        cache.read("../evil", 1)
    cache.close()
