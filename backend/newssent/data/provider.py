"""新聞來源存取介面。

推論層與 API 都只依賴 NewsProvider 這個介面，不直接呼叫 NewsAPI——
這是本專案唯一與不穩定外部服務（NewsAPI 免費層有每日 100 requests 與延遲 24h 限制）
的接觸點。測試一律注入 FakeProvider，不打真實網路。
備援源（yfinance news、Finnhub 免費層）只要另實作本介面即可無痛切換。
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass

from newssent.data.cache import NewsCache, time_bucket, validate_ticker


@dataclass
class Article:
    title: str
    url: str
    published_at: str  # ISO8601 字串
    source: str

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(title=d["title"], url=d["url"], published_at=d["published_at"], source=d["source"])


class NewsResult:
    """一次取新聞的結果，含降級旗標。stale=True 表示外部源失敗、回傳的是舊快取。"""

    def __init__(self, articles: list[Article], stale: bool):
        self.articles = articles
        self.stale = stale


class NewsProviderError(RuntimeError):
    """新聞源無法提供資料，且無可用快取。"""


class NewsProvider(abc.ABC):
    @abc.abstractmethod
    def get_news(self, ticker: str, limit: int) -> NewsResult:
        raise NotImplementedError


class NewsAPIProvider(NewsProvider):
    """以 NewsAPI 為主源，內建 SQLite 時間桶快取與連網失敗降級。

    策略：同一時間桶內有快取直接用；否則呼叫 NewsAPI 並寫入快取；
    呼叫失敗時退回最近一次快取並標記 stale=True，只有連快取都沒有才拋出例外。
    """

    def __init__(self, cache: NewsCache, api_key: str, bucket_seconds: int):
        self._cache = cache
        self._api_key = api_key
        self._bucket_seconds = bucket_seconds

    def get_news(self, ticker: str, limit: int) -> NewsResult:
        validate_ticker(ticker)
        bucket = time_bucket(self._bucket_seconds)

        cached = self._cache.read(ticker, bucket)
        if cached is not None:
            return NewsResult([Article.from_dict(a) for a in cached], stale=False)

        try:
            articles = self._fetch(ticker, limit)
        except Exception as exc:
            fallback = self._cache.read_latest(ticker)
            if fallback is not None:
                return NewsResult([Article.from_dict(a) for a in fallback], stale=True)
            raise NewsProviderError(f"無法取得 {ticker} 的新聞，且無可用快取") from exc

        self._cache.write(ticker, bucket, [a.to_dict() for a in articles])
        return NewsResult(articles, stale=False)

    def _fetch(self, ticker: str, limit: int) -> list[Article]:
        import httpx

        if not self._api_key:
            raise NewsProviderError("未設定 NEWSAPI_KEY（請於 backend/.env 填入）")

        resp = httpx.get(
            "https://newsapi.org/v2/everything",
            params={
                "q": ticker,
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": limit,
                "apiKey": self._api_key,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        payload = resp.json()
        return [
            Article(
                title=a.get("title") or "",
                url=a.get("url") or "",
                published_at=a.get("publishedAt") or "",
                source=(a.get("source") or {}).get("name") or "",
            )
            for a in payload.get("articles", [])
        ]
