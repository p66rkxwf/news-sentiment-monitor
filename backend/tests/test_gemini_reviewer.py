"""GeminiReviewer：與 OllamaReviewer 同一份提示詞；暫時性錯誤重試、額度與設定錯誤大聲失敗。"""

import json

import pytest

from newssent.config import ALERT_SCORER, GEMINI_MODEL
from newssent.inference.llm_review import (
    _SYSTEM_PROMPT,
    GeminiConfigError,
    GeminiQuotaExhausted,
    GeminiReviewer,
)
from newssent.inference.scorers import LlmScorer


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self._body = body
        self.text = json.dumps(body)

    def json(self):
        return self._body


def ok(text: str, thought: str | None = None) -> FakeResponse:
    parts = ([{"text": thought, "thought": True}] if thought else []) + [{"text": text}]
    return FakeResponse(200, {"candidates": [{"content": {"parts": parts}}]})


def quota(per_day: bool, delay: str = "7s") -> FakeResponse:
    quota_id = "GenerateRequestsPerDayPerProjectPerModel-FreeTier" if per_day else "GenerateRequestsPerMinute"
    return FakeResponse(429, {"error": {"code": 429, "details": [
        {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [{"quotaId": quota_id}]},
        {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": delay},
    ]}})


class Scripted:
    """依序回傳預先排好的回應，並記下每次請求。"""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def __call__(self, url, headers, json, timeout):
        self.requests.append({"url": url, "headers": headers, "json": json})
        return self.responses.pop(0)


def make(post, sleeps=None, **kw) -> GeminiReviewer:
    sleeps = sleeps if sleeps is not None else []
    return GeminiReviewer(model="gemma-x", api_key="k", http_post=post, sleep=sleeps.append, **kw)


def test_judges_with_the_shared_prompt():
    post = Scripted(ok('{"label": "negative"}'))
    assert make(post).judge("台積電（2330）", "台積電遭調降評等") == "negative"
    req = post.requests[0]
    assert req["url"].endswith("/models/gemma-x:generateContent")
    assert req["headers"] == {"x-goog-api-key": "k"}
    assert req["json"]["systemInstruction"]["parts"][0]["text"] == _SYSTEM_PROMPT
    assert req["json"]["contents"][0]["parts"][0]["text"] == (
        "Target company: 台積電（2330）\nHeadline: 台積電遭調降評等\n\nJSON answer:"
    )
    assert req["json"]["generationConfig"]["temperature"] == 0.0


def test_system_prompt_moves_into_user_turn_when_unsupported():
    post = Scripted(ok('{"label": "neutral"}'))
    make(post, system_instruction=False).judge("鴻海（2317）", "標題")
    body = post.requests[0]["json"]
    assert "systemInstruction" not in body
    assert body["contents"][0]["parts"][0]["text"].startswith(_SYSTEM_PROMPT)


def test_code_fences_and_thoughts_are_stripped():
    post = Scripted(ok('```json\n{"label": "positive"}\n```', thought="Let me think: positive? negative?"))
    assert make(post).judge("t", "h") == "positive"


def test_per_minute_429_waits_retry_delay_then_succeeds():
    sleeps: list[float] = []
    post = Scripted(quota(per_day=False, delay="7s"), ok('{"label": "neutral"}'))
    assert make(post, sleeps).judge("t", "h") == "neutral"
    assert 8.0 in sleeps  # retryDelay 7s + 1s 餘裕


def test_daily_quota_raises():
    with pytest.raises(GeminiQuotaExhausted):
        make(Scripted(quota(per_day=True))).judge("t", "h")


def test_max_requests_raises_before_calling():
    post = Scripted(ok('{"label": "neutral"}'), ok('{"label": "neutral"}'))
    reviewer = make(post, max_requests=1)
    reviewer.judge("t", "h")
    with pytest.raises(GeminiQuotaExhausted):
        reviewer.judge("t", "h2")
    assert len(post.requests) == 1


@pytest.mark.parametrize("status", [400, 403, 404])
def test_config_errors_fail_loudly(status):
    with pytest.raises(GeminiConfigError):
        make(Scripted(FakeResponse(status, {"error": {"message": "bad"}}))).judge("t", "h")


def test_persistent_server_errors_give_up_with_none():
    post = Scripted(*[FakeResponse(503, {})] * 5)
    assert make(post, retries=4).judge("t", "h") is None
    assert len(post.requests) == 5


def test_unparseable_answer_is_none_not_a_guess():
    assert make(Scripted(ok("I think it could be positive or negative"))).judge("t", "h") is None


def test_paces_requests_to_rpm():
    sleeps: list[float] = []
    reviewer = make(Scripted(ok('{"label": "neutral"}'), ok('{"label": "neutral"}')), sleeps, rpm=30)
    reviewer.judge("t", "a")
    reviewer.judge("t", "b")
    assert len(sleeps) == 1 and 1.9 < sleeps[0] <= 2.0  # 60/30 = 每 2 秒一次


def test_missing_key_is_a_config_error():
    with pytest.raises(GeminiConfigError):
        GeminiReviewer(model="gemma-x", api_key="")


def test_scorer_version_matches_the_online_scorer():
    # API 讀 ALERT_SCORER：預設設定下 recorder 寫入的版本字串必須完全相同，否則看板會是空的
    assert LlmScorer(GeminiReviewer(model=GEMINI_MODEL, api_key="k")).version == ALERT_SCORER
