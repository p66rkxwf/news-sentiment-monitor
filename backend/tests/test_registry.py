"""artifact 版本契約：標籤順序等 metadata 與 config 不一致時必須拒絕載入。"""

import json

import numpy as np
import pytest

from newssent.ml import registry
from newssent.ml.models.baselines import TfidfLogRegModel

_TEXTS = [
    "profit rose sharply this quarter",
    "the company reported record revenue growth",
    "losses widened and sales fell",
    "the firm cut its outlook after weak demand",
    "the board met on tuesday",
    "the company is headquartered in helsinki",
] * 5
_LABELS = [2, 2, 0, 0, 1, 1] * 5


@pytest.fixture
def saved_artifact(tmp_path):
    model = TfidfLogRegModel().fit(_TEXTS, _LABELS)
    registry.save("tfidf_lr", model, metrics={"test": {"macro_f1": 0.9}}, artifacts_dir=tmp_path)
    return tmp_path


def test_roundtrip_load(saved_artifact):
    model, metadata = registry.load("tfidf_lr", artifacts_dir=saved_artifact)
    assert metadata["label_names"] == ["negative", "neutral", "positive"]
    proba = model.predict_proba(["revenue grew strongly"])
    assert proba.shape == (1, 3)
    np.testing.assert_allclose(proba.sum(axis=1), 1.0)


def test_label_order_mismatch_refuses_to_load(saved_artifact):
    meta_path = saved_artifact / "tfidf_lr" / "metadata.json"
    metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    metadata["label_names"] = ["positive", "neutral", "negative"]  # 順序錯位
    meta_path.write_text(json.dumps(metadata), encoding="utf-8")

    with pytest.raises(registry.ArtifactContractError):
        registry.load("tfidf_lr", artifacts_dir=saved_artifact)


def test_missing_artifact_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        registry.load("nonexistent", artifacts_dir=tmp_path)


def test_keywords_exclude_ticker_and_stopwords():
    from newssent.inference.keywords import extract_keywords

    titles = [
        "AAPL beats earnings expectations",
        "AAPL raises guidance on strong iphone demand",
        "the and of to in",  # 全停用詞
    ]
    keywords = [w for w, _ in extract_keywords(titles, "AAPL")]
    assert "aapl" not in [w.lower() for w in keywords]
    assert "earnings" in keywords or "iphone" in keywords
