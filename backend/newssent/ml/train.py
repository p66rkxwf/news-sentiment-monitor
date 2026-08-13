"""統一訓練入口：python -m newssent.ml.train --model tfidf_lr|svm|distilbert|bert|roberta
                                          [--corpus phrasebank|sentfin|combined] [--name 別名]

資料經 phrasebank.prepare()／sentfin.prepare()（自動下載、清洗、去重、固定切分），
訓練後評估 val/test 並以 registry.save() 存 artifact + metadata。
transformer 模型延遲 import torch/transformers：無重相依的環境仍可訓練基線。

--corpus 的意義（實驗 #6）：
  phrasebank  句子層級語氣分類（現行 production 的訓練方式）
  sentfin     目標導向：輸入為 (實體, 標題) 配對，答「這則標題對這個實體是好是壞」
  combined    兩者合併；PhraseBank 樣本無實體，以純標題形式併入（模型需同時吃兩種輸入）
"""

from __future__ import annotations

import argparse
import json
import time

from newssent.data import phrasebank, sentfin
from newssent.ml import registry
from newssent.ml.evaluate import evaluate
from newssent.ml.models.baselines import MODEL_FACTORIES

TRANSFORMER_MODEL_NAMES = ("distilbert", "bert", "roberta")
ALL_MODEL_NAMES = sorted([*MODEL_FACTORIES, *TRANSFORMER_MODEL_NAMES])
CORPUS_CHOICES = ("phrasebank", "sentfin", "combined")


def create_model(name: str, **hyperparams):
    """建立模型實例；transformer 延遲 import 重相依。"""
    if name in TRANSFORMER_MODEL_NAMES:
        from newssent.ml.models.transformer import MODEL_FACTORIES as TRANSFORMER_FACTORIES

        return TRANSFORMER_FACTORIES[name](**hyperparams)
    return MODEL_FACTORIES[name]()


def load_corpus(corpus: str) -> tuple[tuple[list, list], tuple[list, list], tuple[list, list], dict]:
    """回傳 (train, val, test) 三組 (texts, labels) 與要寫進 metadata 的語料資訊。"""
    if corpus == "phrasebank":
        pb = phrasebank.prepare()
        extra = {
            "corpus": "phrasebank",
            "target_dependent": False,
            "n_duplicates_removed": pb.n_duplicates,
        }
        return (
            phrasebank.subset(pb, pb.split.train),
            phrasebank.subset(pb, pb.split.val),
            phrasebank.subset(pb, pb.split.test),
            extra,
        )

    if corpus == "sentfin":
        sf = sentfin.prepare()
        extra = {
            "corpus": "sentfin",
            "target_dependent": True,
            "n_headlines": sf.n_headlines,
            "n_duplicates_removed": sf.n_duplicates,
        }
        return (
            sentfin.subset(sf, sf.split.train),
            sentfin.subset(sf, sf.split.val),
            sentfin.subset(sf, sf.split.test),
            extra,
        )

    pb = phrasebank.prepare()
    sf = sentfin.prepare()
    extra = {
        "corpus": "combined",
        "target_dependent": True,  # 可吃目標導向輸入；無實體時退回純文字
        "n_headlines": sf.n_headlines,
        "n_duplicates_removed": pb.n_duplicates + sf.n_duplicates,
    }

    def merge(part: str) -> tuple[list, list]:
        pb_x, pb_y = phrasebank.subset(pb, getattr(pb.split, part))
        sf_x, sf_y = sentfin.subset(sf, getattr(sf.split, part))
        return pb_x + sf_x, pb_y + sf_y

    return merge("train"), merge("val"), merge("test"), extra


def main() -> None:
    parser = argparse.ArgumentParser(description="訓練情緒分類模型")
    parser.add_argument("--model", required=True, choices=ALL_MODEL_NAMES)
    parser.add_argument("--corpus", default="phrasebank", choices=CORPUS_CHOICES)
    parser.add_argument(
        "--name",
        default=None,
        help="artifact 名稱（預設 phrasebank 用 --model，其他語料用 '<model>-<corpus>'）",
    )
    args = parser.parse_args()

    (train_x, train_y), (val_x, val_y), (test_x, test_y), corpus_extra = load_corpus(args.corpus)
    print(f"語料 {args.corpus}：train/val/test = {len(train_y)}/{len(val_y)}/{len(test_y)}")

    artifact_name = args.name or (
        args.model if args.corpus == "phrasebank" else f"{args.model}-{args.corpus}"
    )

    model = create_model(args.model)
    print(f"訓練 {args.model} → artifact `{artifact_name}`…")
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

    extra = {"n_train": len(train_y), **corpus_extra}
    if hasattr(model, "hyperparams"):
        extra["hyperparams"] = model.hyperparams()
    out_dir = registry.save(artifact_name, model, metrics, extra=extra)
    print(f"artifact 已存入 {out_dir}")


if __name__ == "__main__":
    main()
