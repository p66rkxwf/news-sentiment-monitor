"""統一模型介面：predict_proba 輸出欄位順序固定為 config.LABEL_NAMES。

sklearn 的 classes_ 順序取決於訓練資料，不保證是 0/1/2 完整三類；
此介面把機率欄位對齊到固定順序 [negative, neutral, positive]，缺席類別補 0——
下游（評估、情緒指數、API）永遠拿到 (n, 3) 且欄位語義固定的矩陣。
標籤順序錯位不會報錯、只會默默輸出相反情緒，這裡是第一道防線
（第二道是 registry 的啟動比對）。
"""

from __future__ import annotations

import abc

import numpy as np

from newssent.config import LABEL_NAMES

N_CLASSES = len(LABEL_NAMES)


class SentimentModel(abc.ABC):
    """三分類情緒模型的統一介面。輸入為 clean_text() 後的句子清單。"""

    name: str = "base"

    @abc.abstractmethod
    def fit(
        self,
        texts: list[str],
        labels: list[int],
        val_texts: list[str] | None = None,
        val_labels: list[int] | None = None,
    ) -> "SentimentModel":
        """val_texts/val_labels 供需要 early stopping 的模型（transformer）使用，基線忽略。"""
        raise NotImplementedError

    @abc.abstractmethod
    def predict_proba(self, texts: list[str]) -> np.ndarray:
        """回傳 (n, 3) 機率矩陣，欄位順序 = LABEL_NAMES。"""
        raise NotImplementedError

    def predict(self, texts: list[str]) -> np.ndarray:
        return self.predict_proba(texts).argmax(axis=1)


def align_proba(proba: np.ndarray, classes: np.ndarray) -> np.ndarray:
    """把底層模型輸出的機率欄位對齊到 0..N_CLASSES-1 的固定順序。"""
    aligned = np.zeros((proba.shape[0], N_CLASSES), dtype=np.float64)
    for col, cls in enumerate(classes):
        aligned[:, int(cls)] = proba[:, col]
    return aligned
