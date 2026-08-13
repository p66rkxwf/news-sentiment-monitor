"""去重 + 分層切分（第一週地基，PLAN.md 執行順序 #2）。

PhraseBank 原始資料含重複句；不去重就切分，同一句會同時落在訓練與測試集，
所有模型的比較分數全部虛高。切分必須在任何模型訓練前定案、以固定 seed 可重現，
且全隊共用同一份切分索引，模型比較才公平。

此處刻意不依賴 scikit-learn（骨架階段不裝），以標準庫實作即可，
且對輸入型別無假設（只吃 texts + labels），可用合成資料獨立測試。
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class Split:
    train: list[int]
    val: list[int]
    test: list[int]


def dedup_indices(texts: list[str]) -> list[int]:
    """回傳去重後保留的原始索引（保留每個文字第一次出現的位置，順序穩定）。"""
    seen: set[str] = set()
    kept: list[int] = []
    for i, t in enumerate(texts):
        if t not in seen:
            seen.add(t)
            kept.append(i)
    return kept


def stratified_split(
    labels: list,
    ratios: tuple[float, float, float],
    seed: int,
    indices: list[int] | None = None,
) -> Split:
    """依標籤分層切分為 train/val/test，回傳「原始索引」。

    每個類別內各自依比例切分再合併，確保三個集合的類別分佈與整體一致。
    以固定 seed 洗牌，結果可重現。
    """
    if abs(sum(ratios) - 1.0) > 1e-9:
        raise ValueError(f"ratios 必須加總為 1，收到 {ratios}")

    pool = list(range(len(labels))) if indices is None else list(indices)
    rng = random.Random(seed)

    by_label: dict = {}
    for idx in pool:
        by_label.setdefault(labels[idx], []).append(idx)

    train, val, test = [], [], []
    train_r, val_r, _ = ratios
    for _label, idxs in sorted(by_label.items(), key=lambda kv: str(kv[0])):
        idxs = idxs[:]
        rng.shuffle(idxs)
        n = len(idxs)
        n_train = int(n * train_r)
        n_val = int(n * val_r)
        train += idxs[:n_train]
        val += idxs[n_train : n_train + n_val]
        test += idxs[n_train + n_val :]

    return Split(train=sorted(train), val=sorted(val), test=sorted(test))


def prepare_split(
    texts: list[str],
    labels: list,
    ratios: tuple[float, float, float],
    seed: int,
) -> Split:
    """先去重、再分層切分。回傳的索引皆為原始（未去重前）索引。"""
    kept = dedup_indices(texts)
    return stratified_split(labels, ratios, seed, indices=kept)


def grouped_stratified_split(
    groups: list,
    labels: list,
    ratios: tuple[float, float, float],
    seed: int,
    indices: list[int] | None = None,
) -> Split:
    """以「群組」為單位分層切分——同一群組的所有樣本必落在同一個集合。

    SEntFiN 一則標題可帶多個實體（例：一則標題同時對 A 公司正面、對 B 公司負面），
    展開成多列後若按「列」切分，同一則標題會同時出現在訓練與測試集，
    模型只要背下標題就能答對另一列，測試分數整批虛高。故以標題為群組切分。

    分層以「群組的第一個標籤」為代表（群組通常只有 1-2 列），
    確保三個集合的類別分佈仍大致一致。
    """
    pool = list(range(len(labels))) if indices is None else list(indices)

    members: dict = {}
    for idx in pool:
        members.setdefault(groups[idx], []).append(idx)

    group_keys = sorted(members, key=str)
    group_labels = [labels[members[g][0]] for g in group_keys]
    group_split = stratified_split(group_labels, ratios, seed)

    def expand(group_positions: list[int]) -> list[int]:
        out: list[int] = []
        for pos in group_positions:
            out += members[group_keys[pos]]
        return sorted(out)

    return Split(
        train=expand(group_split.train),
        val=expand(group_split.val),
        test=expand(group_split.test),
    )
