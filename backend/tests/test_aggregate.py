from newssent.inference.aggregate import sentiment_index


def test_empty_is_neutral_zero():
    r = sentiment_index([])
    assert r.score == 0.0
    assert r.label == "neutral"
    assert r.article_count == 0


def test_all_positive():
    r = sentiment_index([("positive", 1.0), ("positive", 1.0)])
    assert r.score == 1.0
    assert r.label == "positive"


def test_all_negative():
    r = sentiment_index([("negative", 1.0), ("negative", 1.0)])
    assert r.score == -1.0
    assert r.label == "negative"


def test_neutral_articles_do_not_move_score():
    r = sentiment_index([("neutral", 0.9), ("neutral", 0.8)])
    assert r.score == 0.0
    assert r.label == "neutral"


def test_mixed_below_threshold_is_neutral():
    # 一正一負互相抵銷，score 落在門檻內 → 中性
    r = sentiment_index([("positive", 0.6), ("negative", 0.6)])
    assert r.score == 0.0
    assert r.label == "neutral"
    assert r.article_count == 2


def test_confidence_weighting():
    # 高信心正面 + 低信心負面 → 淨正
    r = sentiment_index([("positive", 0.9), ("negative", 0.1)])
    assert r.score > 0
    assert r.label == "positive"
