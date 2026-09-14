"""情緒預警的標題評分器：(目標公司, 標題清單) → 每則的 (P負, P中, P正)。

版本字串就是分數庫裡的 scorer 欄位：換模型＝換版本，新舊分數不會混算。

為什麼預設不是 production 的 bert-combined：它以英文語料（PhraseBank＋SEntFiN）訓練，
而台股新聞源（FinMind）是中文標題。BERT 的英文 tokenizer 吃中文不會報錯，輸出卻沒有意義——
「不報錯地輸出錯的東西」正是本專案最要防的失敗型態。
"""

from __future__ import annotations

from typing import Protocol

from newssent.config import LABEL_NAMES
from newssent.inference.llm_review import OllamaReviewer

Proba = tuple[float, float, float]  # 順序 = LABEL_NAMES（negative, neutral, positive）


class HeadlineScorer(Protocol):
    version: str

    def score(self, target: str, titles: list[str]) -> list[Proba | None]:
        """None＝該則評分失敗：不入庫，下次重試（不以猜測值補上）。"""
        ...


class LlmScorer:
    """本機 LLM 目標導向判讀，沿用實驗 #6 B2 組的同一份提示詞（llm_review._SYSTEM_PROMPT）。

    LLM 只給標籤、不給機率，故輸出 one-hot；每日平均分數因此等於
    (正面則數 − 負面則數) / 總則數。
    """

    def __init__(self, reviewer: OllamaReviewer):
        self._reviewer = reviewer
        self.version = f"llm-{reviewer.model}"

    def score(self, target: str, titles: list[str]) -> list[Proba | None]:
        out: list[Proba | None] = []
        for title in titles:
            label = self._reviewer.judge(target, title)
            if label is None:
                out.append(None)
            else:
                out.append(tuple(1.0 if name == label else 0.0 for name in LABEL_NAMES))
        return out
