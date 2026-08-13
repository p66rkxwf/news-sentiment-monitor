from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from newssent.api.deps import get_valid_ticker
from newssent.api.errors import NewsNotFoundError, NewsSourceUnavailableError
from newssent.api.schemas import KeywordScore, NewsItem, NewsResponse, SentimentResponse
from newssent.config import NEWS_DEFAULT_LIMIT, company_name
from newssent.data.provider import NewsProvider, NewsProviderError, NewsResult
from newssent.inference.analyzer import Analyzer

router = APIRouter(prefix="/api/stocks", tags=["sentiment"])


def _fetch_news(request: Request, ticker: str, limit: int) -> NewsResult:
    provider: NewsProvider = request.app.state.news_provider
    try:
        result = provider.get_news(ticker, limit)
    except NewsProviderError as exc:
        raise NewsSourceUnavailableError(str(exc)) from exc
    if not result.articles:
        raise NewsNotFoundError(ticker)
    return result


@router.get("/{ticker}/news", response_model=NewsResponse)
def get_news(
    request: Request,
    ticker: str = Depends(get_valid_ticker),
    limit: int = Query(NEWS_DEFAULT_LIMIT, ge=1, le=100),
) -> NewsResponse:
    result = _fetch_news(request, ticker, limit)

    analyzer: Analyzer | None = getattr(request.app.state, "analyzer", None)
    if analyzer is None:
        # 尚未訓練出 artifact：逐則情緒以 mock 佔位，前端以 is_mock 判斷顯示提示
        items = [
            NewsItem(
                title=a.title,
                url=a.url,
                published_at=a.published_at,
                sentiment="neutral",
                confidence=0.5,
            )
            for a in result.articles
        ]
        return NewsResponse(ticker=ticker, articles=items, stale=result.stale, is_mock=True)

    items = [
        NewsItem(
            title=c.article.title,
            url=c.article.url,
            published_at=c.article.published_at,
            sentiment=c.label,
            confidence=round(c.confidence, 4),
        )
        for c in analyzer.classify(result.articles, target=company_name(ticker))
    ]
    return NewsResponse(ticker=ticker, articles=items, stale=result.stale, is_mock=False)


@router.get("/{ticker}/sentiment", response_model=SentimentResponse)
def get_sentiment(
    request: Request,
    ticker: str = Depends(get_valid_ticker),
    limit: int = Query(NEWS_DEFAULT_LIMIT, ge=1, le=100),
) -> SentimentResponse:
    analyzer: Analyzer | None = getattr(request.app.state, "analyzer", None)
    if analyzer is None:
        # 尚未訓練出 artifact 時的 mock 回應，維持 Phase 0 凍結的欄位結構
        return SentimentResponse(
            ticker=ticker,
            score=0.0,
            label="neutral",
            article_count=0,
            keywords=[],
            model_version="mock-0.0.0",
            as_of=datetime.now(timezone.utc).isoformat(),
            stale=False,
            is_mock=True,
        )

    result = _fetch_news(request, ticker, limit)
    analysis = analyzer.analyze(ticker, result.articles)
    return SentimentResponse(
        ticker=ticker,
        score=analysis.index.score,
        label=analysis.index.label,
        article_count=analysis.index.article_count,
        keywords=[KeywordScore(word=w, score=s) for w, s in analysis.keywords],
        model_version=analyzer.version,
        as_of=datetime.now(timezone.utc).isoformat(),
        stale=result.stale,
        is_mock=False,
    )
