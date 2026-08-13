"""實驗 #6 的守門測試：目標導向輸入格式、群組切分、SEntFiN 解析、LLM 覆核策略。

重點防的是三類「不會報錯但結果全錯」的 bug：
1. 訓練與推論的目標字串組合方式不一致（training/serving skew）
2. 同一標題的多個實體跨切分集合（測試分數整批虛高）
3. LLM 回應解析失敗時偷偷猜一個標籤
"""

from __future__ import annotations

import csv

import pytest

from newssent.data import sentfin
from newssent.ml.dataset import grouped_stratified_split
from newssent.inference.llm_review import ReviewedLabel, _parse_label, hybrid_review
from newssent.text.preprocess import build_target_text, clean_text, split_target_text


class _StubReviewer:
    """固定回覆的假 LLM：測 policy 分流，不打網路。"""

    def __init__(self, answer: str | None):
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def judge(self, target: str, headline: str) -> str | None:
        self.calls.append((target, headline))
        return self.answer


# --- 目標導向輸入格式 ---


def test_build_and_split_target_text_roundtrip():
    combined = build_target_text("Apple", "Apple beats earnings")
    target, body = split_target_text(combined)
    assert target == "Apple"
    assert body == "Apple beats earnings"


def test_build_target_text_without_target_falls_back_to_plain_text():
    combined = build_target_text("", "Market rallies")
    assert combined == "Market rallies"
    assert split_target_text(combined) == (None, "Market rallies")


def test_build_target_text_applies_same_cleaning_as_training():
    # 推論端若少做一次 clean_text，輸入分佈就與訓練不同——這裡釘住兩者同源
    raw_title = "Apple   <b>beats</b>  https://x.com/a estimates"
    assert build_target_text("Apple", raw_title) == build_target_text(
        clean_text("Apple"), clean_text(raw_title)
    )


# --- 群組切分（同一標題不可跨集）---


def test_grouped_split_keeps_same_headline_in_one_bucket():
    titles = [f"headline-{i // 2}" for i in range(40)]  # 每則標題 2 個實體
    labels = [i % 3 for i in range(40)]
    split = grouped_stratified_split(titles, labels, (0.7, 0.15, 0.15), seed=42)

    buckets = {"train": split.train, "val": split.val, "test": split.test}
    for title in set(titles):
        rows = {i for i, t in enumerate(titles) if t == title}
        landed = [name for name, idxs in buckets.items() if rows & set(idxs)]
        assert len(landed) == 1, f"{title} 落在多個集合：{landed}"


def test_grouped_split_covers_every_row_exactly_once():
    titles = [f"h{i // 3}" for i in range(30)]
    labels = [i % 3 for i in range(30)]
    split = grouped_stratified_split(titles, labels, (0.7, 0.15, 0.15), seed=7)
    combined = sorted(split.train + split.val + split.test)
    assert combined == list(range(30))


# --- SEntFiN 解析 ---


def test_sentfin_load_raw_expands_multi_entity_headlines(tmp_path):
    csv_path = tmp_path / "SEntFiN.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["S No.", "Title", "Decisions", "Words"])
        writer.writerow([1, "A up, B down", "{'A': 'positive', 'B': 'negative'}", 4])
        writer.writerow([2, "C flat", "{'C': 'neutral'}", 2])
        writer.writerow([3, "broken row", "not-a-dict", 2])  # 髒資料不得靜默變成標籤

    entities, titles, labels = sentfin.load_raw(csv_path)
    assert entities == ["A", "B", "C"]
    assert titles == ["A up, B down", "A up, B down", "C flat"]
    assert labels == [2, 0, 1]  # positive=2, negative=0, neutral=1


# --- LLM 覆核 ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        ('{"label": "negative"}', "negative"),
        ('  {"label":"POSITIVE"}  ', "positive"),
        ("neutral", "neutral"),
        ("", None),
        ("not json at all", None),
        ('{"label": "bullish"}', None),          # 不在標籤集合內就不猜
        ("it is positive or negative", None),    # 同時命中兩個標籤即視為無法解析
    ],
)
def test_parse_label_never_guesses(raw, expected):
    assert _parse_label(raw) == expected


def test_hybrid_non_neutral_policy_leaves_neutrals_untouched():
    reviewer = _StubReviewer("positive")
    items = [("Apple", "h1", "neutral"), ("Apple", "h2", "negative")]
    out = hybrid_review(items, reviewer, policy="non_neutral")

    assert [r.label for r in out] == ["neutral", "positive"]
    assert [r.source for r in out] == ["model", "llm"]
    assert len(reviewer.calls) == 1  # neutral 那則不該打 LLM


def test_hybrid_all_policy_reviews_everything():
    reviewer = _StubReviewer("negative")
    items = [("Apple", "h1", "neutral"), ("Apple", "h2", "positive")]
    out = hybrid_review(items, reviewer, policy="all")

    assert [r.label for r in out] == ["negative", "negative"]
    assert len(reviewer.calls) == 2


def test_hybrid_falls_back_to_model_label_when_llm_fails():
    reviewer = _StubReviewer(None)  # 解析失敗
    out = hybrid_review([("Apple", "h1", "positive")], reviewer, policy="all")
    assert out == [ReviewedLabel("positive", "model", "positive", None)]


def test_hybrid_rejects_unknown_policy():
    with pytest.raises(ValueError):
        hybrid_review([("Apple", "h1", "neutral")], _StubReviewer("positive"), policy="sometimes")
