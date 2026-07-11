"""評估：Accuracy、Macro F1（主指標）、混淆矩陣、CPU/GPU 推論速度 benchmark。

neutral 過半，Accuracy 會被「全猜 neutral」灌水——多數類基線一併回報，
模型必須明顯超越它才有部署價值（PLAN.md Phase 2）。
GPU 欄位僅對支援 to_device() 的模型（transformer）量測；速度比較分 GPU/CPU
兩欄呈現（部署場景不同結論不同，PLAN.md Phase 3）。
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from newssent.config import LABEL_NAMES
from newssent.ml.models.base import SentimentModel


def evaluate(model: SentimentModel, texts: list[str], labels: list[int]) -> dict[str, Any]:
    y = np.asarray(labels)
    pred = model.predict(texts)
    majority = int(np.bincount(y, minlength=3).argmax())
    return {
        "n_samples": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "macro_f1": float(f1_score(y, pred, average="macro")),
        "majority_class": LABEL_NAMES[majority],
        "majority_baseline_accuracy": float((y == majority).mean()),
        "confusion_matrix": confusion_matrix(y, pred, labels=[0, 1, 2]).tolist(),
        "label_distribution": {LABEL_NAMES[i]: int((y == i).sum()) for i in range(3)},
        "cpu_ms_per_sentence": benchmark_cpu_ms(model, texts),
        "gpu_ms_per_sentence": benchmark_gpu_ms(model, texts),
    }


def benchmark_cpu_ms(model: SentimentModel, texts: list[str], n: int = 200) -> float:
    sample = texts[:n]
    if not sample:
        return float("nan")
    model.predict_proba(sample[:10])  # 暖機（首次呼叫含初始化成本）
    t0 = time.perf_counter()
    model.predict_proba(sample)
    return round((time.perf_counter() - t0) * 1000 / len(sample), 3)


def benchmark_gpu_ms(model: SentimentModel, texts: list[str], n: int = 200) -> float | None:
    """GPU 推論速度；非 transformer 模型或無 CUDA 時回傳 None（表格顯示 —）。"""
    if not hasattr(model, "to_device"):
        return None
    try:
        import torch
    except ImportError:
        return None
    if not torch.cuda.is_available():
        return None

    sample = texts[:n]
    if not sample:
        return None
    try:
        model.to_device("cuda")
        model.predict_proba(sample[:10])  # 暖機（含 kernel 編譯與搬移成本）
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        model.predict_proba(sample)
        torch.cuda.synchronize()
        return round((time.perf_counter() - t0) * 1000 / len(sample), 3)
    finally:
        model.to_device("cpu")  # 量測完搬回 CPU（序列化與部署皆以 CPU 為準）
