"""打亂標籤測試：標籤一打亂，表現就必須崩塌到基線水準。

沒崩塌 → 管線裡有洩漏。設計理由與「抓得到/抓不到什麼」寫在 newssent/ml/leakage.py。

本檔刻意包含兩類測試：
- 崩塌測試（打亂後應回到基線）——真正的把關。
- **對照測試**（已知有洩漏時應判定為紅）——證明把關有牙齒。一條永遠綠的檢查
  等於沒有檢查；沒有這幾條，整條管線壞掉時崩塌測試也會過。

合成語料刻意帶可學的情緒詞，使真標籤**學得到東西**——否則「打亂後掉到基線」
只是因為本來就沒有訊號，證明不了任何事（test_real_labels_beat_shuffled 把關這點）。
"""

import random

import pytest

from newssent.ml.dataset import Split, prepare_split
from newssent.ml.leakage import (
    chance_macro_f1,
    inject_duplicate_texts,
    permute_labels_by_key,
    score_split,
)
from newssent.ml.models.baselines import TfidfLogRegModel

pytestmark = pytest.mark.leakage

_RATIOS = (0.70, 0.15, 0.15)
_SPLIT_SEED = 42
_PERMUTATION_SEED = 20260816

_COMPANIES = ["acme", "borealis", "cygnus", "delta corp", "everest", "fulcrum", "gantry"]
_FILLER = ["reuters reports", "according to filings", "in early trading", "analysts say", ""]

# 三類各自的訊號詞。真標籤下 tfidf_lr 應學得很好；打亂後應完全學不到。
_PHRASES = {
    0: ["plunges after profit warning", "misses estimates", "cuts guidance", "posts wider loss"],
    1: ["names new director", "schedules earnings call", "to hold annual meeting", "files report"],
    2: ["surges on record profit", "beats estimates", "raises guidance", "wins major contract"],
}


def _synthetic_corpus(n_per_class: int = 800, seed: int = 3) -> tuple[list[str], list[int]]:
    rng = random.Random(seed)
    texts: list[str] = []
    labels: list[int] = []
    for label, phrases in _PHRASES.items():
        for i in range(n_per_class):
            company = rng.choice(_COMPANIES)
            phrase = rng.choice(phrases)
            filler = rng.choice(_FILLER)
            texts.append(f"{company} {phrase} {filler} n{i}".strip())
            labels.append(label)
    order = list(range(len(texts)))
    rng.shuffle(order)
    return [texts[i] for i in order], [labels[i] for i in order]


@pytest.fixture(scope="module")
def corpus() -> tuple[list[str], list[int]]:
    return _synthetic_corpus()


@pytest.fixture(scope="module")
def split(corpus) -> Split:
    texts, labels = corpus
    return prepare_split(texts, labels, _RATIOS, seed=_SPLIT_SEED)


@pytest.fixture(scope="module")
def shuffled_labels(corpus) -> list[int]:
    texts, labels = corpus
    return permute_labels_by_key(labels, texts, seed=_PERMUTATION_SEED)


def _model() -> TfidfLogRegModel:
    return TfidfLogRegModel(random_state=0)


@pytest.fixture(scope="module")
def real_score(corpus, split):
    texts, labels = corpus
    return score_split(texts, labels, split, _model)


@pytest.fixture(scope="module")
def shuffled_score(corpus, split, shuffled_labels):
    texts, _ = corpus
    return score_split(texts, shuffled_labels, split, _model)


# === 前置條件 ===============================================================


def test_permutation_keeps_the_label_multiset():
    """置換不得增刪標籤，只改對應關係。"""
    labels = [0, 1, 2, 2, 1, 0, 0, 2]
    keys = [f"t{i}" for i in range(len(labels))]
    out = permute_labels_by_key(labels, keys, seed=1)

    assert sorted(out) == sorted(labels)
    assert out != labels  # 確實被打亂了


def test_same_text_gets_the_same_fake_label():
    """同一段文字的所有列必須拿到同一個假標籤——這是能抓到去重失效的前提。

    逐列獨立置換的話，重複文字會拿到不同假標籤，背下來也沒用，洩漏就藏得住了。
    """
    keys = ["dup", "a", "dup", "b", "dup"]
    labels = [0, 1, 0, 2, 0]
    out = permute_labels_by_key(labels, keys, seed=7)

    dup_positions = [i for i, k in enumerate(keys) if k == "dup"]
    assert len({out[i] for i in dup_positions}) == 1


def test_chance_macro_f1_is_between_zero_and_one(corpus, split):
    texts, labels = corpus
    train = [labels[i] for i in split.train]
    test = [labels[i] for i in split.test]
    assert 0.0 < chance_macro_f1(test, train) < 0.5


# === 主測試：打亂標籤後必須崩塌 =============================================


def test_shuffled_labels_collapse_to_baseline(shuffled_score):
    assert not shuffled_score.leaked(), (
        f"打亂標籤後仍學得到東西，管線有洩漏：{shuffled_score.summary()}"
    )


def test_real_labels_beat_shuffled(real_score, shuffled_score):
    """量表對照：真標籤必須明顯優於打亂版。

    沒有這條，「管線整條壞掉、什麼都學不到」也會讓崩塌測試通過——那是綠燈假象。
    """
    assert real_score.macro_f1 > shuffled_score.macro_f1 + 0.20, (
        f"真標籤 {real_score.summary()}／打亂 {shuffled_score.summary()}"
    )
    assert real_score.leaked() is True  # 有真訊號時，同一組判準本來就該回報「超出基線」


# === 對照測試：已知有洩漏時必須判定為紅 =====================================


def test_detects_duplicate_texts_across_splits(corpus, split, shuffled_labels):
    """測試集文字混進訓練集（去重失效的典型後果）必須被抓到。"""
    texts, _ = corpus
    leaky_split = inject_duplicate_texts(split, n=150)
    score = score_split(texts, shuffled_labels, leaky_split, _model)

    assert score.leaked(), f"注入重複文字後仍未被判定為洩漏：{score.summary()}"
