"""TF-IDF 基線（Phase 2 / 進度 B）。

- tfidf_lr：TF-IDF（uni+bigram）+ LogisticRegression（class_weight='balanced'）
- svm：TF-IDF + LinearSVC，以 CalibratedClassifierCV 校準——LinearSVC 原生無機率，
  但 API 契約要求信心分數，校準後才能輸出 predict_proba。

transformer 模型（Phase 3，需 GPU 與 GB 級下載）之後以同一 SentimentModel
介面加入，訓練/比較流程不變。
"""

from __future__ import annotations

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC

from newssent.ml.models.base import SentimentModel, align_proba


def _vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)


class TfidfLogRegModel(SentimentModel):
    name = "tfidf_lr"

    def __init__(self, random_state: int = 42):
        self._pipe = Pipeline(
            [
                ("tfidf", _vectorizer()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=2000, class_weight="balanced", random_state=random_state
                    ),
                ),
            ]
        )

    def fit(self, texts: list[str], labels: list[int]) -> "TfidfLogRegModel":
        self._pipe.fit(texts, labels)
        return self

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return align_proba(self._pipe.predict_proba(texts), self._pipe.classes_)


class TfidfSvmModel(SentimentModel):
    name = "svm"

    def __init__(self, random_state: int = 42):
        svc = LinearSVC(class_weight="balanced", random_state=random_state)
        self._pipe = Pipeline(
            [
                ("tfidf", _vectorizer()),
                ("clf", CalibratedClassifierCV(svc, cv=5)),
            ]
        )

    def fit(self, texts: list[str], labels: list[int]) -> "TfidfSvmModel":
        self._pipe.fit(texts, labels)
        return self

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        return align_proba(self._pipe.predict_proba(texts), self._pipe.classes_)


MODEL_FACTORIES = {
    "tfidf_lr": TfidfLogRegModel,
    "svm": TfidfSvmModel,
}
