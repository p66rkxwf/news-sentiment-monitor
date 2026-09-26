"""評分器一致性工具的守門測試：κ 與判定方向寫反，會讓「不一致」被報成「可以採用」。"""

from __future__ import annotations

import math

import pytest

from tools import scorer_agreement as sa


def test_kappa_perfect_chance_and_opposite():
    same = [("negative", "negative"), ("neutral", "neutral"), ("positive", "positive")] * 10
    assert sa.cohen_kappa(same) == pytest.approx(1.0)
    # 新評分器永遠答 neutral：一致率 1/3，但 κ＝0（等於猜）
    constant = [(a, "neutral") for a, _ in same]
    assert sa.cohen_kappa(constant) == pytest.approx(0.0)
    swapped = [("negative", "positive"), ("positive", "negative")] * 10
    assert sa.cohen_kappa(swapped) < 0


def test_wilson_interval_contains_point_estimate():
    lo, hi = sa.wilson(80, 100)
    assert lo < 0.8 < hi
    assert all(math.isnan(x) for x in sa.wilson(0, 0))


@pytest.mark.parametrize(
    ("kappa", "coverage", "pairs", "expected"),
    [
        (0.9, 1.0, 100, "不下結論"),  # 樣本不足
        (0.9, 0.5, 5000, "不下結論"),  # 回補未完成
        (0.65, 0.99, 5000, "採用"),
        (0.50, 0.99, 5000, "揭露"),
        (0.30, 0.99, 5000, "暫停"),
    ],
)
def test_verdict_follows_preregistered_thresholds(kappa, coverage, pairs, expected):
    assert expected in sa.verdict(kappa, coverage, pairs)


def test_disclose_verdict_is_not_plain_adopt():
    assert sa.verdict(0.5, 0.99, 5000) != "採用"
