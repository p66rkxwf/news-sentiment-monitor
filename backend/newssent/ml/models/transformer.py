"""Transformer fine-tuning（Phase 3 / 進度 C）：DistilBERT、BERT、RoBERTa。

- HF Trainer + CUDA + fp16 + early stopping（驗證集 Macro F1）+ class weight
  （neutral 過半，WeightedTrainer 覆寫 compute_loss 用 balanced 權重）
- 標籤直接以 config.LABEL_NAMES 的索引 0/1/2 訓練（num_labels=3，id2label 對齊），
  輸出天然符合 SentimentModel 契約，不需 align_proba
- fit 完成後模型固定放 CPU 再走既有 registry 的 joblib 序列化；API 部署場景
  以 CPU 推論為準，GPU benchmark 時再由 to_device() 暫時搬移
- 此模組 import torch/transformers（GB 級相依），由 train.py 延遲載入，
  無 torch 的環境仍可訓練基線
"""

from __future__ import annotations

import tempfile

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch import nn
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    EarlyStoppingCallback,
    Trainer,
    TrainingArguments,
)

from newssent.config import LABEL_NAMES, MAX_LENGTH
from newssent.ml.models.base import N_CLASSES, SentimentModel


class _TextDataset(torch.utils.data.Dataset):
    def __init__(self, encodings: dict, labels: list[int] | None = None):
        self.encodings = encodings
        self.labels = labels

    def __len__(self) -> int:
        return len(self.encodings["input_ids"])

    def __getitem__(self, idx: int) -> dict:
        item = {k: v[idx] for k, v in self.encodings.items()}
        if self.labels is not None:
            item["labels"] = torch.tensor(self.labels[idx], dtype=torch.long)
        return item


class _WeightedTrainer(Trainer):
    """以 balanced class weight 計算 loss（PhraseBank neutral 約 6 成）。"""

    def __init__(self, *args, class_weights: torch.Tensor, **kwargs):
        super().__init__(*args, **kwargs)
        self._class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        loss = nn.CrossEntropyLoss(weight=self._class_weights.to(outputs.logits.device))(
            outputs.logits.view(-1, N_CLASSES), labels.view(-1)
        )
        return (loss, outputs) if return_outputs else loss


def _macro_f1_metric(eval_pred) -> dict[str, float]:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {"macro_f1": float(f1_score(labels, preds, average="macro"))}


class TransformerModel(SentimentModel):
    """三個預訓練模型共用實作；以 pretrained 名稱區分。"""

    def __init__(
        self,
        name: str,
        pretrained: str,
        max_length: int = MAX_LENGTH,
        lr: float = 2e-5,
        epochs: int = 8,
        batch_size: int = 32,
        warmup_ratio: float = 0.1,
        seed: int = 42,
    ):
        self.name = name
        self.pretrained = pretrained
        self.max_length = max_length
        self.lr = lr
        self.epochs = epochs
        self.batch_size = batch_size
        self.warmup_ratio = warmup_ratio
        self.seed = seed
        self._tokenizer = None
        self._model = None
        self._device = "cpu"

    def hyperparams(self) -> dict:
        return {
            "pretrained": self.pretrained,
            "max_length": self.max_length,
            "lr": self.lr,
            "epochs": self.epochs,
            "batch_size": self.batch_size,
            "warmup_ratio": self.warmup_ratio,
        }

    def _encode(self, texts: list[str]):
        return self._tokenizer(
            texts,
            truncation=True,
            padding=True,
            max_length=self.max_length,
            return_tensors="pt",
        )

    def fit(
        self,
        texts: list[str],
        labels: list[int],
        val_texts: list[str] | None = None,
        val_labels: list[int] | None = None,
    ) -> "TransformerModel":
        torch.manual_seed(self.seed)
        self._tokenizer = AutoTokenizer.from_pretrained(self.pretrained)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            self.pretrained,
            num_labels=N_CLASSES,
            id2label=dict(enumerate(LABEL_NAMES)),
            label2id={n: i for i, n in enumerate(LABEL_NAMES)},
        )

        y = np.asarray(labels)
        counts = np.bincount(y, minlength=N_CLASSES).astype(np.float64)
        weights = np.where(
            counts > 0, counts.sum() / (np.count_nonzero(counts) * np.maximum(counts, 1)), 0.0
        )

        train_ds = _TextDataset(self._encode(texts), labels)
        has_val = bool(val_texts) and val_labels is not None
        val_ds = _TextDataset(self._encode(val_texts), val_labels) if has_val else None

        with tempfile.TemporaryDirectory(prefix="hf_trainer_") as tmp_dir:
            args = TrainingArguments(
                output_dir=tmp_dir,
                num_train_epochs=self.epochs,
                per_device_train_batch_size=self.batch_size,
                per_device_eval_batch_size=self.batch_size * 2,
                learning_rate=self.lr,
                warmup_ratio=self.warmup_ratio,
                fp16=torch.cuda.is_available(),
                seed=self.seed,
                logging_steps=50,
                report_to=[],
                # 有驗證集：每 epoch 評估，val Macro F1 選最佳權重 + early stopping
                eval_strategy="epoch" if has_val else "no",
                save_strategy="epoch" if has_val else "no",
                save_total_limit=1,
                load_best_model_at_end=has_val,
                metric_for_best_model="macro_f1",
                greater_is_better=True,
            )
            trainer = _WeightedTrainer(
                model=self._model,
                args=args,
                train_dataset=train_ds,
                eval_dataset=val_ds,
                processing_class=self._tokenizer,
                compute_metrics=_macro_f1_metric if has_val else None,
                callbacks=[EarlyStoppingCallback(early_stopping_patience=2)] if has_val else None,
                class_weights=torch.tensor(weights, dtype=torch.float32),
            )
            trainer.train()

        # 固定放 CPU：joblib 序列化與 API 推論皆以 CPU 為準（部署機不保證有 GPU）
        self._model.cpu().eval()
        self._device = "cpu"
        return self

    def to_device(self, device: str) -> "TransformerModel":
        """evaluate.py 的 GPU benchmark 用；量測完應搬回 cpu。"""
        self._model.to(device)
        self._device = device
        return self

    def predict_proba(self, texts: list[str]) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("模型尚未訓練，請先呼叫 fit()")
        if not texts:
            return np.zeros((0, N_CLASSES), dtype=np.float64)
        self._model.eval()
        outs: list[np.ndarray] = []
        batch = 64
        with torch.no_grad():
            for i in range(0, len(texts), batch):
                enc = self._encode(list(texts[i : i + batch]))
                enc = {k: v.to(self._device) for k, v in enc.items()}
                logits = self._model(**enc).logits
                outs.append(torch.softmax(logits, dim=1).cpu().numpy())
        return np.concatenate(outs).astype(np.float64)

    def __getstate__(self) -> dict:
        # joblib/pickle：確保存檔前權重在 CPU（GPU tensor 直接 pickle 會綁定裝置）
        if self._model is not None:
            self._model.cpu()
        state = self.__dict__.copy()
        state["_device"] = "cpu"
        return state


MODEL_FACTORIES = {
    "distilbert": lambda **kw: TransformerModel(
        name="distilbert", pretrained="distilbert-base-uncased", **kw
    ),
    "bert": lambda **kw: TransformerModel(name="bert", pretrained="bert-base-uncased", **kw),
    "roberta": lambda **kw: TransformerModel(name="roberta", pretrained="roberta-base", **kw),
}
