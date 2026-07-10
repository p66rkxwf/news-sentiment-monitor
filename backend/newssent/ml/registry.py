"""模型 artifact 存取與版本契約（PLAN.md 架構原則 3）。

存檔時一併寫 metadata.json（**標籤順序**、agreement 等級、切分 seed 與比例、
訓練日期、測試指標）；載入時逐項比對當前 config，不一致就拒絕載入——
殺掉「標籤順序錯位後默默輸出相反情緒」這一整類無錯誤訊息的 bug。

metadata.json 進版控（模型權重 model.joblib 由 .gitignore 排除）。
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib

from newssent.config import (
    ARTIFACTS_DIR,
    LABEL_NAMES,
    PHRASEBANK_AGREEMENT,
    SPLIT_RATIOS,
    SPLIT_SEED,
)
from newssent.ml.models.base import SentimentModel


class ArtifactContractError(RuntimeError):
    """artifact metadata 與當前 config 不一致，拒絕載入。"""


def save(
    name: str,
    model: SentimentModel,
    metrics: dict[str, Any],
    extra: dict[str, Any] | None = None,
    artifacts_dir: Path = ARTIFACTS_DIR,
) -> Path:
    out_dir = artifacts_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, out_dir / "model.joblib")

    metadata = {
        "model_name": name,
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "label_names": LABEL_NAMES,
        "phrasebank_agreement": PHRASEBANK_AGREEMENT,
        "split_seed": SPLIT_SEED,
        "split_ratios": list(SPLIT_RATIOS),
        "git_commit": _git_commit(),
        "metrics": metrics,
        **(extra or {}),
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_dir


def load(name: str, artifacts_dir: Path = ARTIFACTS_DIR) -> tuple[SentimentModel, dict[str, Any]]:
    """載入 artifact 並驗證版本契約；不一致拋 ArtifactContractError。"""
    out_dir = artifacts_dir / name
    meta_path = out_dir / "metadata.json"
    model_path = out_dir / "model.joblib"
    if not meta_path.exists() or not model_path.exists():
        raise FileNotFoundError(f"artifact 不存在: {out_dir}")

    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    _check(metadata, "label_names", LABEL_NAMES)
    _check(metadata, "phrasebank_agreement", PHRASEBANK_AGREEMENT)
    _check(metadata, "split_seed", SPLIT_SEED)

    return joblib.load(model_path), metadata


def _check(metadata: dict[str, Any], key: str, expected: Any) -> None:
    actual = metadata.get(key)
    if actual != expected:
        raise ArtifactContractError(
            f"artifact metadata 的 {key} 與當前 config 不一致：\n"
            f"  artifact: {actual!r}\n  config:   {expected!r}\n"
            f"（標籤順序錯位會默默輸出相反情緒）請重新訓練後再啟動。"
        )


def _git_commit() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path(__file__).parent,
        ).stdout.strip()
    except Exception:
        return None
