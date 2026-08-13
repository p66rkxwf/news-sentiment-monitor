"""混合式 LLM 覆核（實驗 #6 的對照組 B）：小模型先篩，本機 LLM 重判。

出處：2026 年對 991 則 NVDA/AMD 標題的實測發現 FinBERT 說「正面」時 83% 是錯的，
提出的解法是 **hybrid**——讓 BERT 處理容易的 neutral、把非中性者交給本機 LLM 重判
（該文回報覆核準確率 84.2%、淨修正 246 則）。本模組把同一設計搬到本專案，
差別是：**我們自己的錯誤型態不只「亂給方向」，還有「抓不到負面」**
（財金組複核：4 則負面模型 0 則抓到，全軟化成 neutral/positive），
故覆核範圍做成可選 policy 並在報告中兩種都量，不直接照抄文獻設定。

刻意不進 production 推論路徑：這是離線比較用的實驗組件，線上是否採用由實證數字決定。
LLM 走本機 Ollama（與 smart-doc-archiver 同一套本機推論基礎設施），不外送任何資料。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from newssent.config import LABEL_NAMES

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_LLM_MODEL = "qwen2.5:14b"

# 覆核範圍：
#   non_neutral 文獻設定——只重判模型給了方向的（修「亂給方向」）
#   all         全部重判（另可修「把負面軟化成 neutral」，成本較高）
REVIEW_POLICIES = ("non_neutral", "all")

# 提示詞刻意寫成與財金組複核相同的原則：
# 「僅憑標題無法確認對該 ticker 的方向就標 neutral」——這才是本專案要答的任務。
_SYSTEM_PROMPT = """You are a financial analyst labelling news headlines for a specific company's stock.

Answer this question: does this headline imply a positive, negative, or neutral outlook FOR THE TARGET COMPANY'S STOCK PRICE?

Rules:
- Judge the impact on the TARGET company only. A headline that is good news for some OTHER company (a supplier, a rival, a different sector) is `neutral` for the target.
- If the headline cannot on its own establish a direction for the target - it is a question, a vague market comment, an opinion piece, or merely mentions the company - answer `neutral`.
- Judge stock-price impact, not the emotional tone of the wording. Dramatic wording alone is not negative.
- Answer with JSON only: {"label": "positive"} or {"label": "negative"} or {"label": "neutral"}."""


@dataclass
class ReviewedLabel:
    """覆核後的最終標籤與其來源（可追溯每一則是誰判的）。"""

    label: str
    source: str            # "model"（未覆核或 LLM 失敗）或 "llm"
    model_label: str
    llm_label: str | None  # LLM 原始判讀；None = 未呼叫或呼叫/解析失敗


class OllamaReviewer:
    """呼叫本機 Ollama 對 (目標, 標題) 做目標導向情緒判讀。"""

    def __init__(
        self,
        model: str = DEFAULT_LLM_MODEL,
        host: str = DEFAULT_OLLAMA_HOST,
        timeout: float = 180.0,
    ):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def available(self) -> bool:
        import httpx

        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=5.0)
            resp.raise_for_status()
            names = {m.get("name", "") for m in resp.json().get("models", [])}
            return self.model in names
        except Exception:
            return False

    def judge(self, target: str, headline: str) -> str | None:
        """回傳 negative/neutral/positive；任何失敗回傳 None（呼叫端維持原標籤，不臆造）。"""
        import httpx

        payload = {
            "model": self.model,
            "prompt": f"Target company: {target}\nHeadline: {headline}\n\nJSON answer:",
            "system": _SYSTEM_PROMPT,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "num_predict": 32},
        }
        try:
            resp = httpx.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return _parse_label(resp.json().get("response", ""))
        except Exception:
            return None


def _parse_label(raw: str) -> str | None:
    """從 LLM 回應取出合法標籤；解析不出來回 None，絕不猜。"""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        label = str(json.loads(raw).get("label", "")).strip().lower()
        if label in LABEL_NAMES:
            return label
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass
    lowered = raw.lower()
    hits = [name for name in LABEL_NAMES if name in lowered]
    return hits[0] if len(hits) == 1 else None


def hybrid_review(
    items: Iterable[tuple[str, str, str]],
    reviewer: OllamaReviewer,
    policy: str = "non_neutral",
) -> list[ReviewedLabel]:
    """items 為 (目標, 標題, 模型標籤) 三元組，依 policy 決定哪些交給 LLM 重判。"""
    if policy not in REVIEW_POLICIES:
        raise ValueError(f"policy 必須是 {REVIEW_POLICIES} 之一，收到 {policy!r}")

    out: list[ReviewedLabel] = []
    for target, headline, model_label in items:
        should_review = policy == "all" or model_label != "neutral"
        if not should_review:
            out.append(ReviewedLabel(model_label, "model", model_label, None))
            continue
        llm_label = reviewer.judge(target, headline)
        if llm_label is None:  # 失敗時退回模型標籤，不讓覆核層自己編一個
            out.append(ReviewedLabel(model_label, "model", model_label, None))
        else:
            out.append(ReviewedLabel(llm_label, "llm", model_label, llm_label))
    return out
