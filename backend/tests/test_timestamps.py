"""時間戳語意：發布時間與抓取時間必須分開，且舊快取要照樣讀得起來。

清單上「每個欄位的時間戳是事件發生／資料發布／你抓到的時間？」那一題，
在程式裡的具體形態就是 Article 的兩個欄位有沒有被混為一談。
"""

import json
import sqlite3
import time
from datetime import datetime

import pytest

from newssent.data.cache import NewsCache
from newssent.data.provider import Article, CachedNewsProvider

pytestmark = pytest.mark.leakage


class _StubProvider(CachedNewsProvider):
    """固定回傳一則沒有 fetched_at 的文章，模擬 _fetch() 的原始輸出。"""

    def _fetch(self, ticker: str, limit: int) -> list[Article]:
        return [
            Article(
                title="Company beats earnings",
                url="https://example.com/1",
                published_at="2026-07-01T09:00:00Z",
                source="Example",
            )
        ]


def test_from_dict_tolerates_cache_written_before_fetched_at_existed():
    """2026-08 之前寫入的快取沒有 fetched_at——舊快取必須照樣讀得起來。

    連網失敗時退回舊快取是既有的可用性設計；為了新欄位把它弄壞，
    等於用一個誠信改善換掉一個可用性保證。
    """
    legacy = {
        "title": "Old headline",
        "url": "https://example.com/old",
        "published_at": "2026-01-01T00:00:00Z",
        "source": "Example",
    }

    article = Article.from_dict(legacy)

    assert article.fetched_at is None
    assert article.title == "Old headline"


def test_roundtrip_preserves_both_timestamps():
    article = Article(
        title="t",
        url="u",
        published_at="2026-07-01T09:00:00Z",
        source="s",
        fetched_at="2026-07-01T12:00:00+00:00",
    )

    assert Article.from_dict(article.to_dict()) == article


def test_get_news_stamps_fetched_at(tmp_path):
    """抓取時間由 CachedNewsProvider 統一蓋章，子類別不必各記各的。"""
    cache = NewsCache(tmp_path / "news.db")
    try:
        provider = _StubProvider(cache, bucket_seconds=3600)
        result = provider.get_news("AAPL", limit=5)

        assert result.articles[0].fetched_at is not None
        # 發布時間來自資料源，不得被抓取時間覆寫
        assert result.articles[0].published_at == "2026-07-01T09:00:00Z"
        assert result.articles[0].fetched_at != result.articles[0].published_at
    finally:
        cache.close()


def test_fetched_at_is_persisted_to_cache(tmp_path):
    """蓋的章要寫進快取——否則下次讀回來又變成 None，落差就量不到了。"""
    cache = NewsCache(tmp_path / "news.db")
    try:
        provider = _StubProvider(cache, bucket_seconds=3600)
        provider.get_news("AAPL", limit=5)

        cached = cache.read_latest("AAPL")
        assert cached is not None
        assert cached[0]["fetched_at"] is not None
    finally:
        cache.close()


def _seed_cache(db_path, article: dict, created_at: float) -> None:
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE IF NOT EXISTS news_cache ("
        "ticker TEXT NOT NULL, bucket INTEGER NOT NULL, payload TEXT NOT NULL, "
        "created_at REAL NOT NULL, PRIMARY KEY (ticker, bucket))"
    )
    conn.execute(
        "INSERT OR REPLACE INTO news_cache VALUES (?, ?, ?, ?)",
        ("AAPL", 1, json.dumps([article]), created_at),
    )
    conn.commit()
    conn.close()


def test_lag_uses_fetched_at_when_present(tmp_path):
    from tools.timestamp_lag import collect_lags

    db = tmp_path / "news.db"
    _seed_cache(
        db,
        {
            "title": "t",
            "url": "u",
            "source": "s",
            "published_at": "2026-07-01T00:00:00+00:00",
            "fetched_at": "2026-07-01T03:00:00+00:00",
        },
        created_at=time.time(),  # 刻意與 fetched_at 差很多，證明用的是 fetched_at
    )

    lags, total, unparsed = collect_lags(db)

    assert (total, unparsed) == (1, 0)
    assert lags[0] == pytest.approx(3.0)


def test_lag_falls_back_to_cache_created_at_for_legacy_rows(tmp_path):
    """舊列沒有 fetched_at 時，退回用該列寫入快取的時刻——歷史資料才量得到落差。"""
    from tools.timestamp_lag import collect_lags

    db = tmp_path / "news.db"
    published = "2026-07-01T00:00:00+00:00"
    # 由 ISO 字串換算 epoch，不寫死魔術數字（寫死很容易差整整一天而不自知）
    published_epoch = datetime.fromisoformat(published).timestamp()
    _seed_cache(
        db,
        {"title": "t", "url": "u", "source": "s", "published_at": published},
        created_at=published_epoch + 7200,  # 發布後 2 小時才抓到
    )

    lags, _, _ = collect_lags(db)

    assert lags[0] == pytest.approx(2.0, abs=0.01)


def test_unparseable_published_at_is_counted_not_crashed(tmp_path):
    from tools.timestamp_lag import collect_lags

    db = tmp_path / "news.db"
    _seed_cache(
        db,
        {"title": "t", "url": "u", "source": "s", "published_at": "not-a-date"},
        created_at=time.time(),
    )

    lags, total, unparsed = collect_lags(db)

    assert (lags, total, unparsed) == ([], 1, 1)
