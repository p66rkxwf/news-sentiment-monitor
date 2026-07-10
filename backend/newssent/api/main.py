import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from newssent.api.errors import ApiError, api_error_handler
from newssent.api.routers import meta, sentiment
from newssent.config import (
    ALLOWED_ORIGINS,
    NEWS_CACHE_BUCKET_SECONDS,
    NEWS_CACHE_DB_PATH,
    NEWSAPI_KEY,
    PRODUCTION_MODEL,
)
from newssent.data.cache import NewsCache
from newssent.data.provider import NewsAPIProvider
from newssent.inference.analyzer import Analyzer
from newssent.ml.registry import ArtifactContractError

logger = logging.getLogger("newssent")

# 每 IP 限流：保護 NewsAPI 每日 100 requests 額度不被單一使用者吃光（PLAN.md 安全性章節）
limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    cache = NewsCache(NEWS_CACHE_DB_PATH)
    app.state.news_cache = cache
    app.state.news_provider = NewsAPIProvider(
        cache=cache,
        api_key=NEWSAPI_KEY,
        bucket_seconds=NEWS_CACHE_BUCKET_SECONDS,
    )

    try:
        app.state.analyzer = Analyzer.from_registry(PRODUCTION_MODEL)
        logger.info("已載入模型 %s", app.state.analyzer.version)
    except FileNotFoundError:
        # 尚未訓練（開發初期）：以 mock 模式提供 API，前端照常對接
        app.state.analyzer = None
        logger.warning("找不到模型 artifact（%s），/sentiment 以 mock 模式運作", PRODUCTION_MODEL)
    except ArtifactContractError:
        # 標籤順序等契約不一致 = 模型會默默輸出相反情緒，寧可拒絕啟動
        raise

    try:
        yield
    finally:
        cache.close()


app = FastAPI(title="News Sentiment Monitor API", lifespan=lifespan)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.add_exception_handler(ApiError, api_error_handler)


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    # 維持 Phase 0 凍結的統一錯誤格式
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "RATE_LIMITED", "message": f"請求過於頻繁（{exc.detail}）"}},
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

app.include_router(meta.router)
app.include_router(sentiment.router)
