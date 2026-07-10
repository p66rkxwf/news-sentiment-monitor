import pytest

from newssent.data.provider import Article, NewsProvider, NewsResult


class FakeProvider(NewsProvider):
    """測試用假 Provider，不打真實網路。"""

    def __init__(self, articles: list[Article], stale: bool = False):
        self._articles = articles
        self._stale = stale

    def get_news(self, ticker: str, limit: int) -> NewsResult:
        return NewsResult(self._articles[:limit], stale=self._stale)


@pytest.fixture
def sample_articles() -> list[Article]:
    return [
        Article(title="Company beats earnings", url="https://example.com/1", published_at="2026-07-01T09:00:00Z", source="Example"),
        Article(title="Analysts upgrade rating", url="https://example.com/2", published_at="2026-07-01T10:00:00Z", source="Example"),
    ]


@pytest.fixture
def client(sample_articles):
    from fastapi.testclient import TestClient

    from newssent.api.main import app

    with TestClient(app) as test_client:
        # 覆蓋 lifespan 建立的真實 provider，注入不打網路的假 provider
        app.state.news_provider = FakeProvider(sample_articles)
        yield test_client


@pytest.fixture
def empty_client():
    """新聞源回傳空清單的情境，用於驗證 404。"""
    from fastapi.testclient import TestClient

    from newssent.api.main import app

    with TestClient(app) as test_client:
        app.state.news_provider = FakeProvider([])
        yield test_client
