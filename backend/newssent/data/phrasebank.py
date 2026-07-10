"""Financial PhraseBank 下載、解析、清洗、去重、分層切分（Phase 1 / 進度 A）。

CLI：python -m newssent.data.phrasebank
  下載資料集 zip（僅數 MB）→ 解析 sentences_50agree → clean_text 清洗 →
  去重 + 分層切分（切分索引存 data/ 進版控，全隊共用同一份切分）→
  產出 docs/data_exploration.md（類別/句長分佈、重複句統計）。

原始檔為 latin-1 編碼、每行「句子@標籤」；標籤為 positive/negative/neutral。
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

from newssent.config import (
    BACKEND_ROOT,
    DATA_DIR,
    LABEL_NAMES,
    LABEL_TO_ID,
    PHRASEBANK_AGREEMENT,
    SPLIT_RATIOS,
    SPLIT_SEED,
)
from newssent.ml.dataset import Split, dedup_indices, prepare_split
from newssent.text.preprocess import clean_text

DOCS_DIR = BACKEND_ROOT.parent / "docs"
ZIP_PATH = DATA_DIR / "FinancialPhraseBank-v1.0.zip"

# 官方原始檔（ResearchGate）需登入，HuggingFace dataset repo 內含同一份 zip
_DOWNLOAD_URLS = [
    "https://huggingface.co/datasets/takala/financial_phrasebank/resolve/main/data/FinancialPhraseBank-v1.0.zip",
    "https://huggingface.co/datasets/financial_phrasebank/resolve/main/data/FinancialPhraseBank-v1.0.zip",
]

_AGREEMENT_TO_FILENAME = {
    "50agree": "Sentences_50Agree.txt",
    "66agree": "Sentences_66Agree.txt",
    "75agree": "Sentences_75Agree.txt",
    "allagree": "Sentences_AllAgree.txt",
}


@dataclass
class PhraseBank:
    """清洗後的語料與固定切分（索引對應 texts/labels 位置）。"""

    texts: list[str]           # clean_text 後的句子（未去重，切分索引已處理去重）
    labels: list[int]          # LABEL_TO_ID 編碼
    split: Split
    n_duplicates: int


def download(dest: Path = ZIP_PATH) -> Path:
    if dest.exists():
        return dest
    import httpx

    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None
    for url in _DOWNLOAD_URLS:
        try:
            resp = httpx.get(url, follow_redirects=True, timeout=60.0)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return dest
        except Exception as exc:  # 換下一個來源
            last_error = exc
    raise RuntimeError(f"PhraseBank 下載失敗（已試 {len(_DOWNLOAD_URLS)} 個來源）") from last_error


def load_raw(agreement: str = PHRASEBANK_AGREEMENT, zip_path: Path = ZIP_PATH) -> tuple[list[str], list[int]]:
    """從 zip 解析原始句子與標籤（未清洗、未去重）。"""
    filename = _AGREEMENT_TO_FILENAME[agreement]
    with zipfile.ZipFile(zip_path) as zf:
        member = next(n for n in zf.namelist() if n.endswith(filename))
        content = zf.read(member).decode("latin-1")

    texts: list[str] = []
    labels: list[int] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        sentence, _, label = line.rpartition("@")
        label = label.strip().lower()
        if label not in LABEL_TO_ID:
            raise ValueError(f"未知標籤 {label!r}（行：{line[:60]}…）")
        texts.append(sentence.strip())
        labels.append(LABEL_TO_ID[label])
    return texts, labels


def prepare(agreement: str = PHRASEBANK_AGREEMENT) -> PhraseBank:
    """下載（如需）→ 清洗 → 去重 + 分層切分。切分索引落地 data/ 供全隊共用。"""
    download()
    raw_texts, labels = load_raw(agreement)
    texts = [clean_text(t) for t in raw_texts]  # 訓練/推論唯一共用清洗入口
    n_duplicates = len(texts) - len(dedup_indices(texts))

    split_path = split_index_path(agreement)
    if split_path.exists():
        payload = json.loads(split_path.read_text(encoding="utf-8"))
        split = Split(train=payload["train"], val=payload["val"], test=payload["test"])
    else:
        split = prepare_split(texts, labels, SPLIT_RATIOS, SPLIT_SEED)
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_path.write_text(
            json.dumps(
                {
                    "agreement": agreement,
                    "seed": SPLIT_SEED,
                    "ratios": SPLIT_RATIOS,
                    "train": split.train,
                    "val": split.val,
                    "test": split.test,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    return PhraseBank(texts=texts, labels=labels, split=split, n_duplicates=n_duplicates)


def split_index_path(agreement: str = PHRASEBANK_AGREEMENT) -> Path:
    return DATA_DIR / f"split_{agreement}_seed{SPLIT_SEED}.json"


def subset(pb: PhraseBank, indices: list[int]) -> tuple[list[str], list[int]]:
    return [pb.texts[i] for i in indices], [pb.labels[i] for i in indices]


def _write_report(pb: PhraseBank, agreement: str) -> None:
    total = len(pb.texts)
    kept = len(pb.split.train) + len(pb.split.val) + len(pb.split.test)
    lengths = sorted(len(t.split()) for t in pb.texts)

    def pct(i: int) -> int:
        return lengths[min(int(len(lengths) * i / 100), len(lengths) - 1)]

    lines = [
        "# 資料探索報告（Phase 1）",
        "",
        f"- 資料集：Financial PhraseBank `sentences_{agreement}`，原始 {total} 筆",
        f"- 重複句：{pb.n_duplicates} 筆（**切分前已去重**，否則同句跨集會讓比較分數虛高）",
        f"- 去重後 {kept} 筆，分層切分 {SPLIT_RATIOS[0]:.0%}/{SPLIT_RATIOS[1]:.0%}/{SPLIT_RATIOS[2]:.0%}"
        f"（seed={SPLIT_SEED}，索引檔 `backend/data/{split_index_path(agreement).name}` 進版控，全隊共用）",
        "",
        "## 類別分佈",
        "",
        "| 集合 | " + " | ".join(LABEL_NAMES) + " | 合計 |",
        "|---|---|---|---|---|",
    ]
    for name, idxs in (("train", pb.split.train), ("val", pb.split.val), ("test", pb.split.test)):
        counts = [sum(1 for i in idxs if pb.labels[i] == c) for c in range(len(LABEL_NAMES))]
        lines.append(f"| {name} | " + " | ".join(map(str, counts)) + f" | {len(idxs)} |")

    all_counts = [sum(1 for i in range(total) if pb.labels[i] == c) for c in range(len(LABEL_NAMES))]
    dist = "、".join(f"{n} {c}（{c / total:.1%}）" for n, c in zip(LABEL_NAMES, all_counts))
    lines += [
        "",
        f"整體分佈：{dist}。",
        "neutral 過半——Accuracy 會被「全猜 neutral」灌水，主指標採 **Macro F1**，",
        "訓練以 class weight 抵銷不平衡（PLAN.md Phase 1）。",
        "",
        "## 句長分佈（詞數）",
        "",
        f"- 中位數 {pct(50)}、P90 {pct(90)}、P99 {pct(99)}、最長 {lengths[-1]}",
        f"- transformer 的 max_length 取 128 已涵蓋 P99（config.MAX_LENGTH）",
        "",
        "> 由 `python -m newssent.data.phrasebank` 自動產生。",
        "",
    ]
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "data_exploration.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out}")


def main() -> None:
    pb = prepare()
    print(
        f"共 {len(pb.texts)} 筆（重複 {pb.n_duplicates}），"
        f"切分 train/val/test = {len(pb.split.train)}/{len(pb.split.val)}/{len(pb.split.test)}"
    )
    _write_report(pb, PHRASEBANK_AGREEMENT)


if __name__ == "__main__":
    main()
