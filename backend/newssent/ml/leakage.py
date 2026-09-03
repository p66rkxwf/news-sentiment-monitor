"""打亂標籤測試（label-permutation null test）——洩漏防治的回歸防線。

把標籤隨機打亂、整條管線原封不動重跑，表現必須崩塌到基線水準。沒崩塌，
就代表管線裡有洩漏。

**它抓得到什麼、抓不到什麼**（不寫清楚，綠燈只是自我安慰）：

- 抓得到：**同一段文字同時落在訓練與測試集**（去重失效）。這正是 dedup_indices()
  存在的理由，也是 PhraseBank 這類含重複句的語料最典型的洩漏。
- 抓得到：任何由標籤衍生出來的特徵、在全語料上 fit 的預處理。
- **抓不到：同標題不同實體跨集**（SEntFiN 的多實體展開）。兩列的文字不同，
  在本測試裡拿到的是各自獨立的假標籤，背下標題也占不到便宜。那條防線是
  grouped_stratified_split() 的以標題為群組切分，由 test_split.py 把關。
  **兩者互補，缺一不可。**

關鍵設計：假標籤以**文字本身為鍵**發放——同一段文字的所有列拿到同一個假標籤。
若改成逐列獨立置換，重複文字會拿到不同假標籤，模型背下來也沒用，去重失效這種
洩漏就變得抓不到，整條測試等於白做。

切分沿用真實標籤算出的那一份（不隨假標籤重算），確保打亂版與真實版只差
「文字↔標籤的對應」一個變因。
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

from newssent.ml.dataset import Split
from newssent.ml.models.base import SentimentModel

# 打亂標籤後允許的殘餘優勢，超過即判定洩漏。
# 文字測試集通常只有數百筆，macro F1 的抽樣噪音比股價那條大，故取 0.05。
TOLERANCE = 0.05


def permute_labels_by_key(
    labels: Sequence[int], keys: Sequence[str], seed: int
) -> list[int]:
    """隨機置換標籤；**同一個 key 的所有列拿到同一個假標籤**。

    key 用文字本身。這樣「同一段文字同時出現在訓練與測試集」時，模型背下它就能
    在測試集答對假標籤，分數不會崩塌——洩漏因此現形。逐列獨立置換則抓不到。
    """
    if len(labels) != len(keys):
        raise ValueError(f"labels 與 keys 長度不符：{len(labels)} vs {len(keys)}")

    first_index: dict[str, int] = {}
    for i, key in enumerate(keys):
        first_index.setdefault(key, i)

    unique_keys = list(first_index)
    pool = [labels[first_index[k]] for k in unique_keys]
    random.Random(seed).shuffle(pool)
    fake_by_key = dict(zip(unique_keys, pool))
    return [fake_by_key[k] for k in keys]


def chance_macro_f1(
    test_labels: Sequence[int], train_labels: Sequence[int], seed: int = 0, draws: int = 50
) -> float:
    """隨機猜測的 macro F1 參考值。

    macro F1 的隨機水準不是 0，也不是 1/3——它取決於類別分佈。與其硬套一個常數，
    直接模擬「依訓練集類別分佈隨機亂猜」的分類器並取平均，得到誠實的比較基準。
    """
    y = np.asarray(test_labels)
    if len(y) == 0:
        return float("nan")

    counts = np.bincount(np.asarray(train_labels, dtype=int), minlength=3).astype(float)
    probs = counts / counts.sum()
    rng = np.random.default_rng(seed)
    scores = [
        f1_score(y, rng.choice(3, size=len(y), p=probs), average="macro", zero_division=0)
        for _ in range(draws)
    ]
    return float(np.mean(scores))


@dataclass(frozen=True)
class PipelineScore:
    """一次「訓練 → 測試」的成績，附帶與兩個基線的距離。"""

    accuracy: float
    macro_f1: float
    majority_baseline: float
    chance_macro_f1: float
    n_train: int
    n_test: int

    @property
    def accuracy_excess(self) -> float:
        return self.accuracy - self.majority_baseline

    @property
    def macro_f1_excess(self) -> float:
        return self.macro_f1 - self.chance_macro_f1

    def leaked(self, tol: float = TOLERANCE) -> bool:
        """單尾判定：打亂標籤後仍明顯**優於**基線才算洩漏。

        低於基線只是噪音或模型無能，不構成洩漏的證據，故不做雙尾。
        """
        return self.accuracy_excess > tol or self.macro_f1_excess > tol

    def summary(self) -> str:
        return (
            f"準確率 {self.accuracy:.4f} vs 多數類基線 {self.majority_baseline:.4f}"
            f"（超出 {self.accuracy_excess:+.4f}）、"
            f"macro F1 {self.macro_f1:.4f} vs 隨機 {self.chance_macro_f1:.4f}"
            f"（超出 {self.macro_f1_excess:+.4f}）、"
            f"訓練 {self.n_train} 筆／測試 {self.n_test} 筆"
        )


def score_split(
    texts: Sequence[str],
    labels: Sequence[int],
    split: Split,
    model_factory: Callable[[], SentimentModel],
) -> PipelineScore:
    """以給定的切分訓練並評估測試集。"""
    train_texts = [texts[i] for i in split.train]
    train_labels = [labels[i] for i in split.train]
    test_texts = [texts[i] for i in split.test]
    test_labels = [labels[i] for i in split.test]

    model = model_factory().fit(train_texts, train_labels)
    pred = model.predict(test_texts)

    y = np.asarray(test_labels)
    majority = int(np.bincount(y, minlength=3).argmax())
    return PipelineScore(
        accuracy=float(accuracy_score(y, pred)),
        macro_f1=float(f1_score(y, pred, average="macro", zero_division=0)),
        majority_baseline=float((y == majority).mean()),
        chance_macro_f1=chance_macro_f1(test_labels, train_labels),
        n_train=len(train_texts),
        n_test=len(test_texts),
    )


# === 刻意注入的洩漏（對照組）=================================================
# 用途只有一個：證明上面那條檢查真的抓得到東西。一條永遠綠的檢查等於沒有檢查。


def inject_duplicate_texts(split: Split, n: int = 100) -> Split:
    """把測試集前 n 列的索引也加進訓練集——模擬「去重失效」。

    這是 dedup_indices() 要防的那件事：同一段文字同時出現在訓練與測試集。
    因為假標籤是以文字為鍵發放的，重複列在兩邊帶著同一個假標籤，模型背下來
    就能在測試集答對——打亂標籤測試因此抓得到它。
    """
    k = min(n, len(split.test))
    return Split(train=split.train + split.test[:k], val=split.val, test=split.test)
