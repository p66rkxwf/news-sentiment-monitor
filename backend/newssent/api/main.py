from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from newssent.api.errors import ApiError, api_error_handler
from newssent.api.routers import meta, sentiment
from newssent.config import (
    ALLOWED_ORIGINS,
    NEWS_CACHE_BUCKET_SECONDS,
    NEWS_CACHE_DB_PATH,
    NEWSAPI_KEY,
)
from newssent.data.cache import NewsCache
from newssent.data.provider import NewsAPIProvider


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = NewsCache(NEWS_CACHE_DB_PATH)
    app.state.news_cache = cache
    app.state.news_provider = NewsAPIProvider(
        cache=cache,
        api_key=NEWSAPI_KEY,
        bucket_seconds=NEWS_CACHE_BUCKET_SECONDS,
    )
    # Phase 4：於此以 newssent/ml/registry.py 載入模型並掛到 app.state.analyzer
    # Phase 5：加入 slowapi 限流，保護 NewsAPI 每日額度
    try:
        yield
    finally:
        cache.close()


app = FastAPI(title="News Sentiment Monitor API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)

app.include_router(meta.router)
app.include_router(sentiment.router)
