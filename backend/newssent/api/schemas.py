"""Pydantic 回應模型 — Phase 0 凍結的 API 契約。

前端從第一週就對這份契約開發（先吃 mock 回應），後續 Phase 不應隨意變更
欄位名稱或型別；若需變更，視為破壞性變更並同步通知前端。
"""

from typing import Literal

from pydantic import BaseModel, Field

SentimentLabel = Literal["negative", "neutral", "positive"]


class KeywordScore(BaseModel):
    word: str
    score: float


class SentimentResponse(BaseModel):
    ticker: str
    score: float = Field(ge=-1, le=1, description="情緒指數，[−1, +1]")
    label: SentimentLabel
    article_count: int
    keywords: list[KeywordScore]
    model_version: str
    as_of: str = Field(description="資料時間戳（ISO8601）")
    stale: bool = Field(default=False, description="外部新聞源失敗、回傳舊快取時為 True")
    is_mock: bool = Field(default=False, description="Phase 5 模型整合前為 True")


class NewsItem(BaseModel):
    title: str
    url: str
    published_at: str
    sentiment: SentimentLabel
    confidence: float = Field(ge=0, le=1)


class NewsResponse(BaseModel):
    ticker: str
    articles: list[NewsItem]
    stale: bool = False
    is_mock: bool = False


class ModelInfoResponse(BaseModel):
    model_version: str
    trained_at: str | None = None
    test_macro_f1: float | None = None
    is_mock: bool = Field(default=False, description="Phase 4 前尚未整合真實模型時為 True")


class HealthResponse(BaseModel):
    status: Literal["ok"]
    model_loaded: bool
