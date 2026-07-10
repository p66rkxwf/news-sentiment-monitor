from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from newssent.api.deps import get_valid_ticker
from newssent.api.errors import NewsNotFoundError, NewsSourceUnavailableError
from newssent.api.schemas import NewsItem, NewsResponse, SentimentResponse
from newssent.config import NEWS_DEFAULT_LIMIT
from newssent.data.provider import NewsProvider, NewsProviderError

router = APIRouter(prefix="/api/stocks", tags=["sentiment"])


@router.get("/{ticker}/news", response_model=NewsResponse)
def get_news(
    request: Request,
    ticker: str = Depends(get_valid_ticker),
    limit: int = Query(NEWS_DEFAULT_LIMIT, ge=1, le=100),
) -> NewsResponse:
    provider: NewsProvider = request.app.state.news_provider
    try:
        result = provider.get_news(ticker, limit)
    except NewsProviderError as exc:
        raise NewsSourceUnavailableError(str(exc)) from exc

    if not result.articles:
        raise NewsNotFoundError(ticker)

    # Phase 5 前：逐則情緒尚未由模型標注，先給 mock 佔位（is_mock=True）
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


@router.get("/{ticker}/sentiment", response_model=SentimentResponse)
def get_sentiment(ticker: str = Depends(get_valid_ticker)) -> SentimentResponse:
    # Phase 5 前的 mock 回應：尚未整合模型與 aggregate，回傳固定結構供前端開發。
    # 待 newssent/inference/analyzer.py 完成後改為真實推論並移除 is_mock。
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
