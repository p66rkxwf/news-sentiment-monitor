"""混合式 LLM 覆核（實驗 #6 的對照組 B）：小模型先篩，本機 LLM 重判。

出處：2026 年對 991 則 NVDA/AMD 標題的實測發現 FinBERT 說「正面」時 83% 是錯的，
提出的解法是 **hybrid**——讓 BERT 處理容易的 neutral、把非中性者交給本機 LLM 重判
（該文回報覆核準確率 84.2%、淨修正 246 則）。本模組把同一設計搬到本專案，
差別是：**我們自己的錯誤型態不只「亂給方向」，還有「抓不到負面」**
（財金組複核：4 則負面模型 0 則抓到，全軟化成 neutral/positive），
故覆核範圍做成可選 policy 並在報告中兩種都量，不直接照抄文獻設定。

刻意不進 production 推論路徑：這是離線比較用的實驗組件，線上是否採用由實證數字決定。
LLM 走本機 Ollama（與 smart-doc-archiver 同一套本機推論基礎設施），不外送任何資料。

情緒預警（alert_recorder）也用同一份提示詞判讀中文標題。2026-09 起雲端排程沒有 GPU、
跑不動本機 27B 模型，改由 GeminiReviewer 呼叫 Google AI Studio 託管的模型——
**這條路徑會把新聞標題送到 Google**（標題本身是公開新聞）。提示詞與解析規則兩者共用
（_SYSTEM_PROMPT / _user_prompt / _parse_label），換的只有推論端點。
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
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


def _user_prompt(target: str, headline: str) -> str:
    """每個 reviewer 共用同一句 user prompt——兩個推論端點只能差在模型，不能差在問法。"""
    return f"Target company: {target}\nHeadline: {headline}\n\nJSON answer:"


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
            "prompt": _user_prompt(target, headline),
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


_CODE_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$")


def _parse_label(raw: str) -> str | None:
    """從 LLM 回應取出合法標籤；解析不出來回 None，絕不猜。"""
    # 託管模型沒有 JSON mode，常把答案包在 ```json ... ``` 裡
    raw = _CODE_FENCE.sub("", (raw or "").strip())
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


DEFAULT_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
_GEMINI_RETRYABLE = frozenset({500, 502, 503, 504})
_GEMINI_CONFIG_ERRORS = frozenset({400, 401, 403, 404})


class GeminiQuotaExhausted(RuntimeError):
    """當日額度用盡或達到本次 max_requests：已評分的都已存檔，額度恢復後重跑即從斷點接續。"""


class GeminiConfigError(RuntimeError):
    """金鑰無效、模型不存在、參數不被接受：不重試、直接中止。

    若回 None，看起來會像「每天都有幾則評分失敗」而永遠沒人發現——設定錯誤必須大聲失敗。
    """


class GeminiReviewer:
    """呼叫 Gemini API（Google AI Studio）託管的模型，做與 OllamaReviewer 相同的目標導向判讀。

    節流：每分鐘不超過 rpm 次（免費層額度以分鐘與日計）。暫時性錯誤（逾時、5xx、每分鐘 429）
    退避重試，用盡則該則回 None（不入庫、下次重試）；當日額度用盡拋 GeminiQuotaExhausted。
    """

    def __init__(
        self,
        model: str,
        api_key: str,
        rpm: float = 25,
        max_requests: int | None = None,
        system_instruction: bool = True,
        max_output_tokens: int = 32,
        timeout: float = 60.0,
        retries: int = 4,
        backoff: float = 10.0,
        base_url: str = DEFAULT_GEMINI_URL,
        http_post: Callable | None = None,
        http_get: Callable | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise GeminiConfigError("未設定 GEMINI_API_KEY")
        self.model = model
        self.version_tag = f"gemini:{model}"
        self.requests = 0
        self._api_key = api_key
        self._min_interval = 60.0 / rpm
        self._max_requests = max_requests
        self._system_instruction = system_instruction
        self._max_output_tokens = max_output_tokens
        self._timeout = timeout
        self._retries = retries
        self._backoff = backoff  # 第 n 次重試前等 backoff × 2^(n-1) 秒（429 另依伺服器給的 retryDelay）
        self._base_url = base_url.rstrip("/")
        self._http_post = http_post
        self._http_get = http_get
        self._sleep = sleep
        self._last_call = float("-inf")

    @property
    def _headers(self) -> dict[str, str]:
        return {"x-goog-api-key": self._api_key}

    def available(self) -> bool:
        import httpx

        try:
            resp = (self._http_get or httpx.get)(
                f"{self._base_url}/models/{self.model}", headers=self._headers, timeout=15.0
            )
            return resp.status_code == 200
        except Exception:
            return False

    def _payload(self, target: str, headline: str) -> dict:
        user = _user_prompt(target, headline)
        # 部分託管模型（例如 Gemma 3）不接受 systemInstruction：改把系統提示放在 user turn 開頭，
        # 與 Ollama 對 gemma3 套用的 chat template 行為相同，提示詞內容不變
        text = user if self._system_instruction else f"{_SYSTEM_PROMPT}\n\n{user}"
        payload: dict = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {"temperature": 0.0, "maxOutputTokens": self._max_output_tokens},
        }
        if self._system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": _SYSTEM_PROMPT}]}
        return payload

    def _post(self, payload: dict):
        import httpx

        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            self._sleep(wait)
        try:
            return (self._http_post or httpx.post)(
                f"{self._base_url}/models/{self.model}:generateContent",
                headers=self._headers,
                json=payload,
                timeout=self._timeout,
            )
        finally:
            self._last_call = time.monotonic()

    def judge(self, target: str, headline: str) -> str | None:
        import httpx

        payload = self._payload(target, headline)
        for attempt in range(self._retries + 1):
            if self._max_requests is not None and self.requests >= self._max_requests:
                raise GeminiQuotaExhausted(f"已達本次呼叫上限 {self._max_requests} 次")
            delay = self._backoff * 2**attempt
            try:
                resp = self._post(payload)
            except httpx.TransportError:  # 逾時、連線中斷：網路暫時性問題
                pass
            else:
                self.requests += 1
                if resp.status_code == 200:
                    return _parse_label(_gemini_text(_json(resp)))
                body = _json(resp)
                if resp.status_code == 429:
                    if _is_daily_quota(body):
                        raise GeminiQuotaExhausted(f"Gemini 當日額度用盡（{self.model}）")
                    delay = _retry_delay(body) or delay
                elif resp.status_code in _GEMINI_CONFIG_ERRORS:
                    message = (body.get("error") or {}).get("message") or resp.text[:200]
                    raise GeminiConfigError(f"Gemini {resp.status_code}（{self.model}）：{message}")
                elif resp.status_code not in _GEMINI_RETRYABLE:
                    return None
            if attempt < self._retries:
                self._sleep(delay)
        return None


def _json(resp) -> dict:
    try:
        body = resp.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _gemini_text(body: dict) -> str:
    """取第一個候選的文字；略過模型的 thinking 片段（part.thought=true）。被安全過濾擋下時回空字串。"""
    candidates = body.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(p.get("text", "") for p in parts if not p.get("thought"))


def _is_daily_quota(body: dict) -> bool:
    return "PerDay" in json.dumps(body)


def _retry_delay(body: dict) -> float | None:
    for detail in (body.get("error") or {}).get("details") or []:
        raw = str(detail.get("retryDelay") or "")
        if raw.endswith("s"):
            try:
                return float(raw[:-1]) + 1.0
            except ValueError:
                return None
    return None


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
