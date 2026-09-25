"""Pydantic 回應模型 — Phase 0 凍結的 API 契約。

前端從第一週就對這份契約開發（先吃 mock 回應），後續 Phase 不應隨意變更
欄位名稱或型別；若需變更，視為破壞性變更並同步通知前端。
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

SentimentLabel = Literal["negative", "neutral", "positive"]
AlertLevelName = Literal["high", "watch", "normal", "insufficient"]


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


# --- 情緒異常預警（GET /api/alerts）---


class DailySentimentPoint(BaseModel):
    session: date
    score: float | None = Field(description="該交易日標題平均分數 P(正)−P(負)；null＝當日無標題")
    article_count: int


class AlertEvidence(BaseModel):
    title: str
    source: str
    published_at: str = Field(description="發布時間（ISO8601，UTC）")
    score: float


class StockAlert(BaseModel):
    ticker: str
    name: str
    level: AlertLevelName
    reason: str | None = Field(default=None, description="insufficient 時說明缺什麼")
    z_score: float | None
    score_today: float | None = Field(description="當日情緒分數，[−1, +1]")
    baseline_mean: float | None = Field(description="前 20 個交易日分數平均（不含當日）")
    baseline_std: float | None
    score_change: float | None = Field(description="當日分數 − 基準平均")
    article_count: int
    baseline_days: int = Field(description="基準期中有標題的交易日數")
    recent_score: float | None = Field(description="近 5 個交易日依則數加權的分數")
    recent: list[DailySentimentPoint]
    evidence: list[AlertEvidence] = Field(description="當日最負面的標題（最多 3 則），供人工覆核")


class AlertSummary(BaseModel):
    high: int
    watch: int
    normal: int
    insufficient: int = Field(description="資料不足、無法判斷的股票數（不等於正常）")


class AlertSessionsResponse(BaseModel):
    sessions: list[date] = Field(description="可查詢的交易日（遞增）；末端可能含推估的未來交易日")
    latest: date = Field(description="GET /api/alerts 省略 as_of 時採用的交易日")


class AlertsResponse(BaseModel):
    as_of: date
    window_closed: bool = Field(description="false＝該交易日尚未開盤，標題仍在累積、結果可能再變")
    scorer: str
    params: dict[str, float]
    universe_size: int
    summary: AlertSummary
    alerts: list[StockAlert]
