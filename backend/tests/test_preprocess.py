from newssent.text.preprocess import clean_text


def test_strips_urls_and_html():
    raw = 'Great quarter! <b>Read</b> more at https://example.com/news'
    cleaned = clean_text(raw)
    assert "http" not in cleaned
    assert "<b>" not in cleaned
    assert "Great quarter!" in cleaned


def test_collapses_whitespace():
    assert clean_text("a\n\n  b\t c") == "a b c"


def test_empty_input():
    assert clean_text("") == ""


def test_idempotent():
    # parity 的基礎：訓練與推論可能各清洗一次，結果必須相同
    raw = "Shares   rose <i>3%</i> today  http://x.com "
    once = clean_text(raw)
    assert clean_text(once) == once


def test_does_not_lowercase():
    # 大小寫交由各模型 tokenizer 處理，clean_text 不可提前破壞
    assert clean_text("Apple TSLA") == "Apple TSLA"
