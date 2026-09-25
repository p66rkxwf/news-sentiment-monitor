"""裁判資格考的守門測試：不打網路、不呼叫 Codex。

重點防的是「不會報錯但結果全錯」的四類 bug：
1. 裁判偷用工具（讀檔可能讀到人工標注）卻沒被擋下
2. 裁判少答、多答或答非法標籤時被悄悄接受或補猜
3. 判讀規則與 gemma3/qwen 用的那份不同，數字失去可比性
4. 合格判定的方向寫反，或未作答被當成答對
"""

from __future__ import annotations

import json

import pytest

from newssent.inference.llm_review import _SYSTEM_PROMPT
from tools.judge_qualify import (
    MISSING,
    audit_events,
    build_prompt,
    cohen_kappa,
    judge_rules,
    mcnemar,
    parse_batch_output,
    score,
    verdict,
)


def _events(*item_types: str) -> str:
    lines = [{"type": "thread.started"}, {"type": "turn.started"}]
    lines += [{"type": "item.completed", "item": {"type": t}} for t in item_types]
    lines.append({"type": "turn.completed", "usage": {"input_tokens": 1}})
    return "\n".join(json.dumps(x) for x in lines)


# --- 事件稽核 ---


def test_audit_passes_plain_answer():
    assert audit_events(_events("reasoning", "agent_message")) == []


@pytest.mark.parametrize("tool", ["command_execution", "file_change", "web_search", "mcp_tool_call"])
def test_audit_flags_any_tool_call(tool):
    assert audit_events(_events(tool, "agent_message")) == [tool]


def test_audit_flags_failed_turn_and_garbage():
    bad = audit_events('{"type": "turn.failed"}\nnot json')
    assert "turn.failed" in bad and "unparseable-event" in bad


# --- 作答解析 ---


def _answer(pairs):
    return json.dumps({"labels": [{"id": i, "label": lab} for i, lab in pairs]})


def test_parse_accepts_exact_answer_set():
    out = parse_batch_output(_answer([("q01", "negative"), ("q02", "neutral")]), ["q01", "q02"])
    assert out == {"q01": "negative", "q02": "neutral"}


@pytest.mark.parametrize(
    "pairs",
    [
        [("q01", "negative")],  # 少答
        [("q01", "negative"), ("q02", "neutral"), ("q03", "positive")],  # 多答
        [("q01", "negative"), ("q01", "neutral")],  # 重複 id
        [("q01", "negative"), ("q02", "bullish")],  # 非法標籤
    ],
)
def test_parse_rejects_whole_batch_on_any_mismatch(pairs):
    assert parse_batch_output(_answer(pairs), ["q01", "q02"]) is None


def test_parse_rejects_non_json():
    assert parse_batch_output("q01: negative", ["q01"]) is None


# --- 判讀規則與過去的 LLM 裁判同一份 ---


def test_rules_are_verbatim_prefix_of_llm_review_prompt():
    rules = judge_rules()
    assert _SYSTEM_PROMPT.startswith(rules)
    assert "Answer with JSON only" not in rules  # 單則作答格式已拿掉，改用批次 schema


def test_prompt_is_blind_to_model_output():
    prompt = build_prompt([("Apple", "Apple beats earnings")])
    assert "q01 | Apple | Apple beats earnings" in prompt
    assert "model" not in prompt.lower().split("items")[1]  # 題目區不含任何模型判讀


# --- 計分與裁決 ---


def test_kappa_perfect_and_chance():
    assert cohen_kappa(["negative", "neutral"], ["negative", "neutral"]) == pytest.approx(1.0)
    assert cohen_kappa(["negative", "positive"] * 2, ["negative", "negative", "positive", "positive"]) == 0.0


def test_missing_counts_as_wrong():
    s = score(["negative", "neutral"], [MISSING, "neutral"])
    assert s["agreement"] == 0.5 and s["missing"] == 1 and s["neg_hit"] == 0


def test_mcnemar_counts_discordant_cells():
    human = ["negative"] * 10
    model = ["neutral"] * 10
    judge = ["negative"] * 10
    a_only, b_only, p = mcnemar(human, model, judge)
    assert (a_only, b_only) == (0, 10) and p < 0.01


def _stats(agreement, neg_recall=1.0, kappa=0.9):
    return {"agreement": agreement, "neg_recall": neg_recall, "neg_hit": 1, "neg_total": 1, "kappa": kappa}


def test_strict_requires_beating_model_significantly():
    assert verdict("strict", _stats(0.80), _stats(0.60), 0.01)[0] is True
    assert verdict("strict", _stats(0.80), _stats(0.60), 0.20)[0] is False  # 贏但不顯著
    assert verdict("strict", _stats(0.60), _stats(0.80), 0.01)[0] is False  # 顯著但方向相反
    assert verdict("strict", _stats(0.80, neg_recall=0.5), _stats(0.60), 0.01)[0] is False


def test_strict_refuses_without_model_preds():
    with pytest.raises(ValueError):
        verdict("strict", _stats(0.8), None, None)


def test_lenient_thresholds():
    assert verdict("lenient", _stats(0.70, kappa=0.50), None, None)[0] is True
    assert verdict("lenient", _stats(0.69, kappa=0.90), None, None)[0] is False
