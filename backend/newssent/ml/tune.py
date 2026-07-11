"""Transformer 超參數搜尋：python -m newssent.ml.tune --model bert

小型 grid search（PLAN.md Phase 4）：learning rate × max_length，
以驗證集 Macro F1 選優，最佳模型連同超參數經 registry.save 存回
artifacts/<model>/（覆蓋 train.py 的預設超參數版本）。
基線模型（tfidf_lr/svm）不在此調參範圍。
"""

from __future__ import annotations

import argparse
import itertools
import json
import time

from newssent.data import phrasebank
from newssent.ml import registry
from newssent.ml.evaluate import evaluate
from newssent.ml.train import TRANSFORMER_MODEL_NAMES, create_model

# 依 docs/data_exploration.md 句長分佈（P99 遠低於 128），max_length 只需比較 64/128
GRID = {
    "lr": [1e-5, 2e-5, 3e-5],
    "max_length": [64, 128],
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Transformer 超參數搜尋")
    parser.add_argument("--model", required=True, choices=TRANSFORMER_MODEL_NAMES)
    args = parser.parse_args()

    pb = phrasebank.prepare()
    train_x, train_y = phrasebank.subset(pb, pb.split.train)
    val_x, val_y = phrasebank.subset(pb, pb.split.val)
    test_x, test_y = phrasebank.subset(pb, pb.split.test)
    print(f"train/val/test = {len(train_y)}/{len(val_y)}/{len(test_y)}")

    keys = list(GRID)
    results: list[dict] = []
    best = None
    for combo in itertools.product(*(GRID[k] for k in keys)):
        params = dict(zip(keys, combo))
        t0 = time.perf_counter()
        model = create_model(args.model, **params)
        model.fit(train_x, train_y, val_texts=val_x, val_labels=val_y)
        val = evaluate(model, val_x, val_y)
        seconds = time.perf_counter() - t0
        row = {**params, "val_macro_f1": val["macro_f1"], "seconds": round(seconds, 1)}
        results.append(row)
        print(json.dumps(row, ensure_ascii=False))
        if best is None or val["macro_f1"] > best["val"]["macro_f1"]:
            best = {"params": params, "model": model, "val": val, "seconds": seconds}

    assert best is not None
    print(f"\n最佳組合（驗證 Macro F1 {best['val']['macro_f1']:.4f}）: {best['params']}")

    metrics = {
        "val": best["val"],
        "test": evaluate(best["model"], test_x, test_y),
        "train_seconds": round(best["seconds"], 1),
    }
    print(json.dumps({k: v for k, v in metrics["test"].items() if k != "confusion_matrix"},
                     ensure_ascii=False, indent=2))

    extra = {
        "n_train": len(train_y),
        "n_duplicates_removed": pb.n_duplicates,
        "hyperparams": best["model"].hyperparams(),
        "tuned": True,
        "tuning_grid": GRID,
        "tuning_results": results,
    }
    out_dir = registry.save(args.model, best["model"], metrics, extra=extra)
    print(f"最佳模型已存入 {out_dir}")


if __name__ == "__main__":
    main()
