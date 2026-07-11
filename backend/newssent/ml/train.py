"""統一訓練入口：python -m newssent.ml.train --model tfidf_lr|svm|distilbert|bert|roberta

資料經 phrasebank.prepare()（自動下載、清洗、去重、固定切分），
訓練後評估 val/test 並以 registry.save() 存 artifact + metadata。
transformer 模型延遲 import torch/transformers：無重相依的環境仍可訓練基線。
"""

from __future__ import annotations

import argparse
import json
import time

from newssent.data import phrasebank
from newssent.ml import registry
from newssent.ml.evaluate import evaluate
from newssent.ml.models.baselines import MODEL_FACTORIES

TRANSFORMER_MODEL_NAMES = ("distilbert", "bert", "roberta")
ALL_MODEL_NAMES = sorted([*MODEL_FACTORIES, *TRANSFORMER_MODEL_NAMES])


def create_model(name: str, **hyperparams):
    """建立模型實例；transformer 延遲 import 重相依。"""
    if name in TRANSFORMER_MODEL_NAMES:
        from newssent.ml.models.transformer import MODEL_FACTORIES as TRANSFORMER_FACTORIES

        return TRANSFORMER_FACTORIES[name](**hyperparams)
    return MODEL_FACTORIES[name]()


def main() -> None:
    parser = argparse.ArgumentParser(description="訓練情緒分類模型")
    parser.add_argument("--model", required=True, choices=ALL_MODEL_NAMES)
    args = parser.parse_args()

    pb = phrasebank.prepare()
    train_x, train_y = phrasebank.subset(pb, pb.split.train)
    val_x, val_y = phrasebank.subset(pb, pb.split.val)
    test_x, test_y = phrasebank.subset(pb, pb.split.test)
    print(f"train/val/test = {len(train_y)}/{len(val_y)}/{len(test_y)}")

    model = create_model(args.model)
    print(f"訓練 {args.model}…")
    t0 = time.perf_counter()
    model.fit(train_x, train_y, val_texts=val_x, val_labels=val_y)
    train_seconds = round(time.perf_counter() - t0, 1)
    print(f"訓練完成，耗時 {train_seconds}s")

    metrics = {
        "val": evaluate(model, val_x, val_y),
        "test": evaluate(model, test_x, test_y),
        "train_seconds": train_seconds,
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    extra = {"n_train": len(train_y), "n_duplicates_removed": pb.n_duplicates}
    if hasattr(model, "hyperparams"):
        extra["hyperparams"] = model.hyperparams()
    out_dir = registry.save(args.model, model, metrics, extra=extra)
    print(f"artifact 已存入 {out_dir}")


if __name__ == "__main__":
    main()
