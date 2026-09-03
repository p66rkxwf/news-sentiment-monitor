"""新聞來源存取介面。

推論層與 API 都只依賴 NewsProvider 這個介面，不直接呼叫外部服務——
這是本專案唯一與不穩定外部源的接觸點。測試一律注入 FakeProvider，不打真實網路。

- YFinanceNewsProvider：免金鑰、近即時（目前主源，config.NEWS_PROVIDER）
- NewsAPIProvider：申請表指定源（免費層每日 100 requests、延遲 24h），
  取得金鑰後於 config 一行切回
兩者共用 CachedNewsProvider 的「時間桶快取 → 連網 → 失敗退回快取(stale)」策略。
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone

from newssent.data.cache import NewsCache, time_bucket, validate_ticker


@dataclass
class Article:
    """一則新聞，帶**兩個**時間戳——分清楚才知道模型是何時看得到這則消息的。

    - published_at：資料源宣稱的**發布時間**（NewsAPI 的 publishedAt／yfinance 的
      pubDate）。注意這是「發布」不是「事件發生」——事件本身可能更早，
      有時早很多（財報是盤後公布，但財報期間是三個月）。資料源不提供事件時間，
      這個落差無法從資料裡補回來，只能誠實承認。
    - fetched_at：**我們抓到的時間**。這才是資訊真正進到系統的時刻，
      線上情緒指數的可用時點由它決定，不是由 published_at 決定。

    兩者的實測落差見 docs/timestamp_semantics.md（由 tools/timestamp_lag.py 產生）。
    """

    title: str
    url: str
    published_at: str  # ISO8601 字串；資料源宣稱的發布時間
    source: str
    fetched_at: str | None = None  # ISO8601 字串；本系統實際取得的時間

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        # fetched_at 用 .get()：2026-08 之前寫入的快取沒有這個欄位，
        # 舊快取必須照樣讀得起來（降級退回舊快取是既有的可用性設計）
        return cls(
            title=d["title"],
            url=d["url"],
            published_at=d["published_at"],
            source=d["source"],
            fetched_at=d.get("fetched_at"),
        )


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


class CachedNewsProvider(NewsProvider):
    """時間桶快取 + 失敗降級的共用外殼；子類只需實作 _fetch()。

    策略：同一時間桶內有快取直接用；否則呼叫外部源並寫入快取；
    呼叫失敗時退回最近一次快取並標記 stale=True，只有連快取都沒有才拋出例外。
    """

    def __init__(self, cache: NewsCache, bucket_seconds: int):
        self._cache = cache
        self._bucket_seconds = bucket_seconds

    def get_news(self, ticker: str, limit: int) -> NewsResult:
        validate_ticker(ticker)
        bucket = time_bucket(self._bucket_seconds)

        cached = self._cache.read(ticker, bucket)
        if cached is not None:
            return NewsResult([Article.from_dict(a) for a in cached], stale=False)

        try:
            # 抓取時間統一在這裡蓋章，不交給各子類別——兩個來源才不會各記各的
            articles = [
                replace(a, fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"))
                for a in self._fetch(ticker, limit)
            ]
        except Exception as exc:
            fallback = self._cache.read_latest(ticker)
            if fallback is not None:
                return NewsResult([Article.from_dict(a) for a in fallback], stale=True)
            raise NewsProviderError(f"無法取得 {ticker} 的新聞，且無可用快取") from exc

        self._cache.write(ticker, bucket, [a.to_dict() for a in articles])
        return NewsResult(articles, stale=False)

    @abc.abstractmethod
    def _fetch(self, ticker: str, limit: int) -> list[Article]:
        raise NotImplementedError


class NewsAPIProvider(CachedNewsProvider):
    """NewsAPI 源（申請表指定；免費層每日 100 requests、文章延遲 24h）。"""

    def __init__(self, cache: NewsCache, api_key: str, bucket_seconds: int):
        super().__init__(cache, bucket_seconds)
        self._api_key = api_key

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


class YFinanceNewsProvider(CachedNewsProvider):
    """yfinance 新聞源：免金鑰、近即時（Yahoo Finance 非官方介面）。

    yfinance 改版史上 news payload 有兩種格式，_to_article 需雙格式防禦解析：
    - 新版（0.2.5x+）：{'id', 'content': {'title', 'pubDate'(ISO8601),
      'canonicalUrl': {'url'}, 'clickThroughUrl': {'url'}, 'provider': {'displayName'}}}
    - 舊版：{'title', 'link', 'publisher', 'providerPublishTime'(epoch 秒)}
    """

    def _fetch(self, ticker: str, limit: int) -> list[Article]:
        import yfinance as yf

        raw = yf.Ticker(ticker).get_news(count=limit)
        articles = [a for a in (_to_article(item) for item in raw or []) if a is not None]
        if not articles:
            raise NewsProviderError(f"yfinance 未回傳 {ticker} 的任何新聞")
        return articles[:limit]


def _to_article(item: dict) -> Article | None:
    """把 yfinance 新/舊兩種 payload 轉為 Article；無標題者濾除。"""
    if not isinstance(item, dict):
        return None

    content = item.get("content")
    if isinstance(content, dict):  # 新版格式
        title = (content.get("title") or "").strip()
        if not title:
            return None
        url = (content.get("canonicalUrl") or {}).get("url") or (
            content.get("clickThroughUrl") or {}
        ).get("url") or ""
        provider = (content.get("provider") or {}).get("displayName") or ""
        return Article(
            title=title,
            url=url,
            published_at=content.get("pubDate") or "",
            source=provider,
        )

    # 舊版格式
    title = (item.get("title") or "").strip()
    if not title:
        return None
    epoch = item.get("providerPublishTime")
    published = (
        datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="seconds")
        if isinstance(epoch, (int, float))
        else ""
    )
    return Article(
        title=title,
        url=item.get("link") or "",
        published_at=published,
        source=item.get("publisher") or "",
    )
