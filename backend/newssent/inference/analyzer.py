"""線上情緒分析：新聞標題 → clean_text → 模型逐則情緒 → 聚合指數 + 關鍵字。

Analyzer 不碰網路——新聞由呼叫端經 NewsProvider 取得後傳入；
文字一律走 clean_text() 同一入口，與訓練路徑一致（架構原則 4）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from newssent.config import ARTIFACTS_DIR, LABEL_NAMES
from newssent.data.provider import Article
from newssent.inference.aggregate import SentimentIndex, sentiment_index
from newssent.inference.keywords import extract_keywords
from newssent.ml import registry


@dataclass
class ArticleSentiment:
    article: Article
    label: str
    confidence: float


@dataclass
class AnalysisResult:
    index: SentimentIndex
    articles: list[ArticleSentiment]
    keywords: list[tuple[str, float]]


class Analyzer:
    def __init__(self, model, metadata: dict[str, Any]):
        self._model = model
        self.metadata = metadata

    @classmethod
    def from_registry(cls, name: str, artifacts_dir: Path = ARTIFACTS_DIR) -> "Analyzer":
        model, metadata = registry.load(name, artifacts_dir)
        return cls(model, metadata)

    @property
    def version(self) -> str:
        return f"{self.metadata['model_name']}-{self.metadata['trained_at'][:10]}"

    def classify(self, articles: list[Article]) -> list[ArticleSentiment]:
        from newssent.text.preprocess import clean_text

        if not articles:
            return []
        texts = [clean_text(a.title) for a in articles]
        proba = self._model.predict_proba(texts)
        out = []
        for article, p in zip(articles, proba):
            idx = int(p.argmax())
            out.append(
                ArticleSentiment(article=article, label=LABEL_NAMES[idx], confidence=float(p[idx]))
            )
        return out

    def analyze(self, ticker: str, articles: list[Article]) -> AnalysisResult:
        from newssent.text.preprocess import clean_text

        classified = self.classify(articles)
        index = sentiment_index([(c.label, c.confidence) for c in classified])
        keywords = extract_keywords([clean_text(a.title) for a in articles], ticker)
        return AnalysisResult(index=index, articles=classified, keywords=keywords)
