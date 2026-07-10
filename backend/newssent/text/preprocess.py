"""文字前處理的唯一共用入口 clean_text()。

transformers 的 tokenizer 綁定於模型本身，training/serving skew 的風險集中在
「清洗規則」與「標籤映射」。訓練與推論都必須呼叫同一個 clean_text()，並以
parity 測試（test_preprocess.py）保證兩條路徑逐值相等。

刻意不做小寫化：交由各模型的 tokenizer / TfidfVectorizer 依自身慣例處理，
避免在此處提前破壞大小寫資訊而造成基線與 transformer 的輸入不一致。
"""

import re
import unicodedata

_URL_RE = re.compile(r"https?://\S+|www\.\S+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """正規化財經新聞文字：Unicode 正規化、去 URL/HTML、壓縮空白。

    確定性、冪等（clean_text(clean_text(x)) == clean_text(x)）——parity 測試依賴此性質。
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = _URL_RE.sub(" ", text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()
