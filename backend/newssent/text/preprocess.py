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


# --- 目標導向（target-dependent）輸入 ---
# 「這則標題對『誰』是好消息」才是本專案要答的問題：同一則標題可能對 A 公司正面、
# 對 B 公司無關（例：「Tim Cook 給記憶體股好消息」對 MU 正面、對 AAPL 中性）。
# 因此輸入不只是標題，而是（目標實體, 標題）配對。此分隔符是訓練與推論的唯一契約，
# transformer 端會在 tokenize 時把它還原成真正的 sentence-pair（token_type_ids 正確），
# 不依賴任何特定模型的 [SEP] 字面值。
TARGET_DELIM = " ||| "


def build_target_text(target: str, text: str) -> str:
    """組出目標導向輸入字串；target 為空時退回純標題（與舊句子層級模型相容）。"""
    target = clean_text(target)
    text = clean_text(text)
    if not target:
        return text
    return f"{target}{TARGET_DELIM}{text}"


def split_target_text(combined: str) -> tuple[str | None, str]:
    """還原 (目標, 標題)；非目標導向字串回傳 (None, 原字串)。"""
    if TARGET_DELIM not in combined:
        return None, combined
    target, _, text = combined.partition(TARGET_DELIM)
    return target, text
