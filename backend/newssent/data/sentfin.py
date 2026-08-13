"""SEntFiN 1.0 下載、解析、展開、群組切分（實驗 #6：目標導向情緒）。

CLI：python -m newssent.data.sentfin

**為什麼要換語料**：現行模型訓練於 Financial PhraseBank——分析師標注的財報／公告
短句，量的是「語氣（tone）」。但線上要答的是「這則**標題**對**這支股票**是不是好消息
（price impact）」，兩者是不同任務。2026 年對 991 則 NVDA/AMD 標題的實測顯示，主流
FinBERT 說「正面」時有 83% 是錯的，作者的診斷即「模型是為錯的任務訓練的」。
財金組複核我們自己的模型時給的標注原則——「僅憑標題無法確認對該 ticker 的方向就標
neutral」——正是文獻裡的 **entity-aware / target-dependent sentiment**。

SEntFiN 1.0（Sinha et al., JASIST 2022；MIT 授權）就是為此建的資料集：
10,753 則**新聞標題**、標注到**實體層級**，其中 2,847 則含多個實體且情緒互相衝突。

原始格式：`S No., Title, Decisions, Words`，Decisions 為 Python dict 字面值
（如 `{'Infosys': 'neutral', 'TCS': 'positive'}`）。一則標題展開成多列 (實體, 標題)。

誠實限制：SEntFiN 取自印度財經媒體，實體多為印度上市公司；本專案線上跑的是美股。
語體（標題、疑問句、多實體並列）相符，但**實體分佈不同**——這是已知的領域落差，
不可宣稱已完全消除，最終仍以人工抽測（docs/online_spot_check.md）驗收。
"""

from __future__ import annotations

import ast
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from newssent.config import (
    BACKEND_ROOT,
    DATA_DIR,
    LABEL_TO_ID,
    SPLIT_RATIOS,
    SPLIT_SEED,
)
from newssent.ml.dataset import Split, dedup_indices, grouped_stratified_split
from newssent.text.preprocess import build_target_text, clean_text

DOCS_DIR = BACKEND_ROOT.parent / "docs"
CSV_PATH = DATA_DIR / "SEntFiN.csv"

# MIT 授權、作者自建的公開 repo（論文 arXiv:2305.12257 指定來源）
_DOWNLOAD_URLS = [
    "https://raw.githubusercontent.com/pyRis/SEntFiN/main/SEntFiN.csv",
]


@dataclass
class SentFiN:
    """展開後的 (實體, 標題) 樣本與固定切分。"""

    texts: list[str]        # build_target_text(entity, title)：訓練與推論的同一組合格式
    labels: list[int]
    entities: list[str]
    titles: list[str]       # 群組切分的鍵：同一標題不跨集
    split: Split
    n_headlines: int
    n_duplicates: int


def download(dest: Path = CSV_PATH) -> Path:
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
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"SEntFiN 下載失敗（已試 {len(_DOWNLOAD_URLS)} 個來源）") from last_error


def load_raw(csv_path: Path = CSV_PATH) -> tuple[list[str], list[str], list[int]]:
    """解析 CSV 並把 Decisions 展開成逐 (實體, 標題) 列（未清洗、未去重）。"""
    entities: list[str] = []
    titles: list[str] = []
    labels: list[int] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            title = (row.get("Title") or "").strip()
            raw_decisions = (row.get("Decisions") or "").strip()
            if not title or not raw_decisions:
                continue
            try:
                decisions = ast.literal_eval(raw_decisions)
            except (ValueError, SyntaxError):
                continue  # 少數格式異常列直接跳過，不讓髒資料靜默污染標籤
            if not isinstance(decisions, dict):
                continue
            for entity, sentiment in decisions.items():
                label = str(sentiment).strip().lower()
                if label not in LABEL_TO_ID or not str(entity).strip():
                    continue
                entities.append(str(entity).strip())
                titles.append(title)
                labels.append(LABEL_TO_ID[label])
    return entities, titles, labels


def prepare(csv_path: Path = CSV_PATH) -> SentFiN:
    """下載（如需）→ 展開 → 清洗成目標導向文字 → 去重 + 依標題群組切分。"""
    download(csv_path)
    raw_entities, raw_titles, labels = load_raw(csv_path)

    entities = [clean_text(e) for e in raw_entities]
    titles = [clean_text(t) for t in raw_titles]
    texts = [build_target_text(e, t) for e, t in zip(entities, titles)]
    kept = dedup_indices(texts)
    n_duplicates = len(texts) - len(kept)

    split_path = split_index_path()
    if split_path.exists():
        payload = json.loads(split_path.read_text(encoding="utf-8"))
        split = Split(train=payload["train"], val=payload["val"], test=payload["test"])
    else:
        split = grouped_stratified_split(titles, labels, SPLIT_RATIOS, SPLIT_SEED, indices=kept)
        split_path.parent.mkdir(parents=True, exist_ok=True)
        split_path.write_text(
            json.dumps(
                {
                    "corpus": "sentfin",
                    "seed": SPLIT_SEED,
                    "ratios": SPLIT_RATIOS,
                    "grouped_by": "title",
                    "train": split.train,
                    "val": split.val,
                    "test": split.test,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    return SentFiN(
        texts=texts,
        labels=labels,
        entities=entities,
        titles=titles,
        split=split,
        n_headlines=len(set(titles)),
        n_duplicates=n_duplicates,
    )


def split_index_path() -> Path:
    return DATA_DIR / f"split_sentfin_seed{SPLIT_SEED}.json"


def subset(ds: SentFiN, indices: list[int]) -> tuple[list[str], list[int]]:
    return [ds.texts[i] for i in indices], [ds.labels[i] for i in indices]


def _write_report(ds: SentFiN) -> None:
    from newssent.config import LABEL_NAMES

    total = len(ds.texts)
    kept = len(ds.split.train) + len(ds.split.val) + len(ds.split.test)
    multi = total - ds.n_headlines

    lines = [
        "# SEntFiN 1.0 資料探索（實驗 #6：目標導向情緒）",
        "",
        f"- 資料集：SEntFiN 1.0（Sinha et al., JASIST 2022；arXiv:2305.12257；MIT 授權）",
        f"- {ds.n_headlines} 則新聞標題，展開成 **{total} 筆 (實體, 標題) 樣本**"
        f"（多實體標題貢獻 {multi} 筆額外樣本）",
        f"- 重複樣本 {ds.n_duplicates} 筆（切分前去重），去重後 {kept} 筆",
        f"- 切分 {SPLIT_RATIOS[0]:.0%}/{SPLIT_RATIOS[1]:.0%}/{SPLIT_RATIOS[2]:.0%}"
        f"（seed={SPLIT_SEED}），**以標題為群組**：同一則標題的多個實體必落在同一集合，"
        "否則模型背下標題即可答對另一列，測試分數整批虛高。",
        f"- 索引檔 `backend/data/{split_index_path().name}` 進版控。",
        "",
        "## 類別分佈",
        "",
        "| 集合 | " + " | ".join(LABEL_NAMES) + " | 合計 |",
        "|---|---|---|---|---|",
    ]
    for name, idxs in (("train", ds.split.train), ("val", ds.split.val), ("test", ds.split.test)):
        counts = [sum(1 for i in idxs if ds.labels[i] == c) for c in range(len(LABEL_NAMES))]
        lines.append(f"| {name} | " + " | ".join(map(str, counts)) + f" | {len(idxs)} |")

    all_counts = [sum(1 for i in range(total) if ds.labels[i] == c) for c in range(len(LABEL_NAMES))]
    dist = "、".join(f"{n} {c}（{c / total:.1%}）" for n, c in zip(LABEL_NAMES, all_counts))
    lines += [
        "",
        f"整體分佈：{dist}。",
        "",
        "## 與 PhraseBank 的差別（為什麼要換）",
        "",
        "| | Financial PhraseBank（現行） | SEntFiN 1.0（本實驗） |",
        "|---|---|---|",
        "| 文本型態 | 分析師標注的財報／公告短句 | **新聞標題** |",
        "| 標注對象 | 整句語氣（tone） | **特定實體**（target-dependent） |",
        "| 多實體衝突 | 無此概念 | 2,847 則標題含多實體、情緒可互相衝突 |",
        "| 與線上任務距離 | 領域外：語體與任務都不同 | 語體相符；實體分佈仍是印度股市（誠實限制） |",
        "",
        "> 由 `python -m newssent.data.sentfin` 自動產生。",
        "",
    ]
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "data_exploration_sentfin.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out}")


def main() -> None:
    ds = prepare()
    print(
        f"標題 {ds.n_headlines} 則 → 樣本 {len(ds.texts)} 筆（重複 {ds.n_duplicates}），"
        f"切分 train/val/test = {len(ds.split.train)}/{len(ds.split.val)}/{len(ds.split.test)}"
    )
    _write_report(ds)


if __name__ == "__main__":
    main()
