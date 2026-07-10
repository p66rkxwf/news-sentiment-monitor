"""彙整 artifacts/*/metadata.json 產出模型比較表：python -m newssent.ml.compare

輸出 Markdown 到 docs/model_comparison.md。Phase 3 的 transformer 模型
訓練完存入 artifacts/ 後，重跑本指令即自動併入同一張表。
"""

from __future__ import annotations

import json
from pathlib import Path

from newssent.config import ARTIFACTS_DIR, BACKEND_ROOT, LABEL_NAMES

DOCS_DIR = BACKEND_ROOT.parent / "docs"


def build_table(artifacts_dir: Path = ARTIFACTS_DIR) -> str:
    rows = []
    for meta_path in sorted(artifacts_dir.glob("*/metadata.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        test = meta.get("metrics", {}).get("test", {})
        val = meta.get("metrics", {}).get("val", {})
        rows.append(
            {
                "模型": meta["model_name"],
                "驗證 Macro F1": _fmt(val.get("macro_f1")),
                "測試 Macro F1": _fmt(test.get("macro_f1")),
                "測試 Accuracy": _fmt(test.get("accuracy")),
                "多數類基線 Acc": _fmt(test.get("majority_baseline_accuracy")),
                "CPU ms/句": test.get("cpu_ms_per_sentence", "—"),
                "GPU ms/句": test.get("gpu_ms_per_sentence", "—"),
                "訓練日": meta.get("trained_at", "")[:10],
            }
        )
    if not rows:
        return "（尚無任何 artifact，先執行 python -m newssent.ml.train）\n"

    headers = list(rows[0])
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row[h]) for h in headers) + " |")
    return "\n".join(lines) + "\n"


def _fmt(value) -> str:
    return f"{value:.4f}" if isinstance(value, (int, float)) else "—"


def main() -> None:
    table = build_table()
    doc = (
        "# 模型比較報告\n\n"
        f"三分類（{ ' / '.join(LABEL_NAMES) }），去重後分層切分（全隊共用同一份切分索引），"
        "主指標 Macro F1（neutral 過半，Accuracy 會被灌水）。\n\n"
        f"{table}\n"
        "> 由 `python -m newssent.ml.compare` 自動產生，數據來源為 "
        "`backend/artifacts/*/metadata.json`。GPU 欄位待 Phase 3 transformer 加入。\n"
    )
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "model_comparison.md"
    out.write_text(doc, encoding="utf-8")
    print(table)
    print(f"已寫入 {out}")


if __name__ == "__main__":
    main()
