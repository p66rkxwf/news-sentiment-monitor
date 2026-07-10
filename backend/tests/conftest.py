import pytest

from newssent.data.provider import Article, NewsProvider, NewsResult
from newssent.inference.aggregate import sentiment_index
from newssent.inference.analyzer import AnalysisResult, ArticleSentiment


class FakeProvider(NewsProvider):
    """測試用假 Provider，不打真實網路。"""

    def __init__(self, articles: list[Article], stale: bool = False):
        self._articles = articles
        self._stale = stale

    def get_news(self, ticker: str, limit: int) -> NewsResult:
        return NewsResult(self._articles[:limit], stale=self._stale)


class FakeAnalyzer:
    """測試用假 Analyzer：固定判 positive/0.9，不需要真實 artifact。"""

    version = "fake-1.0"
    metadata = {
        "model_name": "fake",
        "trained_at": "2026-01-01T00:00:00+00:00",
        "metrics": {"test": {"macro_f1": 0.72}},
    }

    def classify(self, articles: list[Article]) -> list[ArticleSentiment]:
        return [
            ArticleSentiment(article=a, label="positive", confidence=0.9) for a in articles
        ]

    def analyze(self, ticker: str, articles: list[Article]) -> AnalysisResult:
        classified = self.classify(articles)
        return AnalysisResult(
            index=sentiment_index([(c.label, c.confidence) for c in classified]),
            articles=classified,
            keywords=[("earnings", 1.0)],
        )


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
        app.state.limiter.enabled = False  # 測試逐案累計會誤觸限流
        # 覆蓋 lifespan 建立的真實 provider，注入不打網路的假 provider
        app.state.news_provider = FakeProvider(sample_articles)
        # 測試不依賴本機是否已訓練出 artifact：預設走 mock 路徑
        app.state.analyzer = None
        yield test_client


@pytest.fixture
def client_with_model(sample_articles):
    from fastapi.testclient import TestClient

    from newssent.api.main import app

    with TestClient(app) as test_client:
        app.state.limiter.enabled = False
        app.state.news_provider = FakeProvider(sample_articles)
        app.state.analyzer = FakeAnalyzer()
        yield test_client


@pytest.fixture
def empty_client():
    """新聞源回傳空清單的情境，用於驗證 404。"""
    from fastapi.testclient import TestClient

    from newssent.api.main import app

    with TestClient(app) as test_client:
        app.state.limiter.enabled = False
        app.state.news_provider = FakeProvider([])
        app.state.analyzer = None
        yield test_client
