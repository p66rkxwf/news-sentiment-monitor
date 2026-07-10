"""統一訓練入口：python -m newssent.ml.train --model tfidf_lr|svm

資料經 phrasebank.prepare()（自動下載、清洗、去重、固定切分），
訓練後評估 val/test 並以 registry.save() 存 artifact + metadata。
transformer 模型（Phase 3）之後加入 MODEL_FACTORIES 即可用同一入口。
"""

from __future__ import annotations

import argparse
import json
import time

from newssent.data import phrasebank
from newssent.ml import registry
from newssent.ml.evaluate import evaluate
from newssent.ml.models.baselines import MODEL_FACTORIES


def main() -> None:
    parser = argparse.ArgumentParser(description="訓練情緒分類模型")
    parser.add_argument("--model", required=True, choices=sorted(MODEL_FACTORIES))
    args = parser.parse_args()

    pb = phrasebank.prepare()
    train_x, train_y = phrasebank.subset(pb, pb.split.train)
    val_x, val_y = phrasebank.subset(pb, pb.split.val)
    test_x, test_y = phrasebank.subset(pb, pb.split.test)
    print(f"train/val/test = {len(train_y)}/{len(val_y)}/{len(test_y)}")

    model = MODEL_FACTORIES[args.model]()
    print(f"訓練 {args.model}…")
    t0 = time.perf_counter()
    model.fit(train_x, train_y)
    train_seconds = round(time.perf_counter() - t0, 1)
    print(f"訓練完成，耗時 {train_seconds}s")

    metrics = {
        "val": evaluate(model, val_x, val_y),
        "test": evaluate(model, test_x, test_y),
        "train_seconds": train_seconds,
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))

    out_dir = registry.save(
        args.model,
        model,
        metrics,
        extra={"n_train": len(train_y), "n_duplicates_removed": pb.n_duplicates},
    )
    print(f"artifact 已存入 {out_dir}")


if __name__ == "__main__":
    main()
