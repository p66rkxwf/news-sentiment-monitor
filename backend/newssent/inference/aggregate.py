"""情緒指數：把逐則新聞的情緒與信心，聚合成單一 [−1, +1] 指標。

純函式、參數讀 config，可獨立測試邊界值（全正/全負/空清單/全中性）。
公式：score = Σ(sign(label) × confidence) / n，neutral 的 sign 為 0（不貢獻極性）。
"""

from __future__ import annotations

from dataclasses import dataclass

from newssent.config import SENTIMENT_LABEL_THRESHOLD, SENTIMENT_SIGN


@dataclass
class SentimentIndex:
    score: float          # [−1, +1]
    label: str            # negative / neutral / positive
    article_count: int


def sentiment_index(
    labeled: list[tuple[str, float]],
    threshold: float = SENTIMENT_LABEL_THRESHOLD,
) -> SentimentIndex:
    """labeled: [(label, confidence), ...]。

    空清單回傳中性、score 0。score 超過門檻判正、低於負門檻判負，區間內為中性。
    """
    n = len(labeled)
    if n == 0:
        return SentimentIndex(score=0.0, label="neutral", article_count=0)

    total = 0.0
    for label, confidence in labeled:
        sign = SENTIMENT_SIGN.get(label, 0)
        total += sign * confidence
    score = total / n

    if score > threshold:
        label = "positive"
    elif score < -threshold:
        label = "negative"
    else:
        label = "neutral"

    return SentimentIndex(score=round(score, 4), label=label, article_count=n)
