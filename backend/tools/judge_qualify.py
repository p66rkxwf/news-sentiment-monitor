"""裁判資格考：Codex 能不能當情緒標籤的裁判？依 docs/judge_qualification_prereg.md 執行。

「讓 agent 驗證模型、反覆優化」的前提是裁判比被評的模型準；否則迴圈只會把模型調成
裁判的樣子。快取數據（盲判、同一批 60 則）：gemma3:27b 一致率 60.0%（κ=0.34）、
qwen2.5:14b 51.7%（κ=0.17），都沒贏過被評的 bert-combined（61.7%）——都不合格。
新裁判必須先在財金組已標注的 120 則上考過，才可進入優化迴圈。

防裁判偷看答案：
- 題目只給 (公司名, 標題)，不給模型判讀或信心值（盲判）；判讀規則與 gemma3/qwen 同一份
- Codex 在空的暫存目錄、read-only 沙箱、--ignore-user-config、--ephemeral 下執行
- read-only 沙箱**不擋讀檔**，所以真正的防線是事件稽核：每批的 JSONL 事件中出現任何
  工具呼叫（執行指令、讀寫檔、網頁搜尋）→ 該批作廢、不寫快取

用法（backend/ 目錄執行）:
    python tools/judge_qualify.py smoke          # 3 則自編標題試通管線（不碰考題）
    python tools/judge_qualify.py export-preds   # [GPU 機] 匯出 bert-combined 對 120 則的判讀
    python tools/judge_qualify.py run            # 考試；預先聲明與本檔須已 commit
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import datetime, timezone
from math import comb
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from newssent.config import LABEL_NAMES, company_name  # noqa: E402

DOCS_DIR = BACKEND_ROOT.parent / "docs"
EXAM_CSVS = [
    DOCS_DIR / "spot_check_sample_2026-07-17.csv",
    DOCS_DIR / "spot_check_sample.csv",  # 08-05 批
    DOCS_DIR / "spot_check_sample_2026-08-14.csv",
]
PREREG_MD = DOCS_DIR / "judge_qualification_prereg.md"
CACHE_CSV = DOCS_DIR / "judge_qualification_labels.csv"
PREDS_CSV = DOCS_DIR / "judge_qualification_model_preds.csv"
REPORT_MD = DOCS_DIR / "judge_qualification.md"

# --- 預先聲明的規則：改任何一項都必須先改 docs/judge_qualification_prereg.md 並 commit，再重跑 ---
PASS_RULE: str | None = "strict"  # "strict" | "lenient"；None＝尚未選定，run 拒絕執行
STRICT_ALPHA = 0.05  # 嚴格：一致率高於被評模型且 McNemar（雙尾）p < α
STRICT_MIN_NEG_RECALL = 0.60  # 嚴格：人工判負面者，裁判至少抓到這個比例
LENIENT_MIN_AGREEMENT = 0.70  # 寬鬆：一致率門檻
LENIENT_MIN_KAPPA = 0.50  # 寬鬆：Cohen's κ 門檻
N_EXAM = 120
JUDGE_MODEL = "gpt-6-astra"
JUDGE_EFFORT = "medium"
BATCH_SIZE = 10
SHUFFLE_SEED = 20260923
MAX_ATTEMPTS = 3  # 單批最多嘗試次數；仍失敗者計分時算錯（保守，不補判）
MODEL_ARTIFACT = "bert-combined"

MISSING = "missing"  # 裁判沒給出合法標籤；計分時一律算錯
ALLOWED_ITEM_TYPES = {"agent_message", "reasoning"}  # 其餘 item 類型都是工具呼叫
CODEX_FALLBACK_BIN = "/Applications/ChatGPT.app/Contents/Resources/codex"  # macOS ChatGPT 桌面版內附
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["labels"],
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["id", "label"],
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string", "enum": list(LABEL_NAMES)},
                },
            },
        }
    },
}

SMOKE_ITEMS = [  # 自編、不在考題內；只驗管線，不寫快取
    ("Acme Robotics", "Acme Robotics cuts full-year revenue guidance as orders slump"),
    ("Zenith Foods", "Is Zenith Foods a buy ahead of earnings?"),
    ("Nova Semis", "Nova Semis wins multi-year supply deal with major automaker"),
]


def judge_key() -> str:
    return f"codex:{JUDGE_MODEL}:{JUDGE_EFFORT}"


# --- 考題與快取 ---


def load_exam_rows(paths: list[Path] | None = None, expected: int | None = N_EXAM) -> list[dict]:
    """三批財金組盲標，依 (ticker, title) 去重；題數與預先聲明不符就拒絕（考題不可悄悄變少）。"""
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path in paths or EXAM_CSVS:
        if not path.exists():
            raise SystemExit(f"缺少考題檔 {path.name}")
        batch = path.stem.replace("spot_check_sample", "").strip("_") or "2026-08-05"
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                human = (row.get("human_label") or "").strip().lower()
                title = (row.get("title") or "").strip()
                ticker = (row.get("ticker") or "").strip().upper()
                key = (ticker, title)
                if human not in LABEL_NAMES or not title or key in seen:
                    continue
                seen.add(key)
                rows.append({"batch": batch, "ticker": ticker, "title": title, "human": human})
    if expected is not None and len(rows) != expected:
        raise SystemExit(f"考題應為 {expected} 則，實際讀到 {len(rows)} 則——與預先聲明不符，停止")
    return rows


def load_cache() -> dict[tuple[str, str], str]:
    if not CACHE_CSV.exists():
        return {}
    with open(CACHE_CSV, encoding="utf-8-sig", newline="") as f:
        return {
            (r["ticker"], r["title"]): r["label"]
            for r in csv.DictReader(f)
            if r.get("judge") == judge_key() and r.get("label") in LABEL_NAMES
        }


def append_cache(rows: list[dict], labels: dict[str, str], batch_id: str) -> None:
    """每批判完立刻落地，中途斷線不必重判已完成的批次。"""
    new_file = not CACHE_CSV.exists()
    judged_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(CACHE_CSV, "a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "title", "judge", "label", "batch_id", "judged_at"])
        if new_file:
            writer.writeheader()
        for qid, r in zip(_ids(len(rows)), rows):
            writer.writerow(
                {
                    "ticker": r["ticker"],
                    "title": r["title"],
                    "judge": judge_key(),
                    "label": labels[qid],
                    "batch_id": batch_id,
                    "judged_at": judged_at,
                }
            )


def load_model_preds() -> dict[tuple[str, str], str]:
    if not PREDS_CSV.exists():
        return {}
    with open(PREDS_CSV, encoding="utf-8-sig", newline="") as f:
        return {
            (r["ticker"], r["title"]): r["model_label"]
            for r in csv.DictReader(f)
            if r.get("artifact") == MODEL_ARTIFACT and r.get("model_label") in LABEL_NAMES
        }


# --- Codex 呼叫 ---


def judge_rules() -> str:
    """判讀規則沿用 llm_review 給 gemma3/qwen 的同一份（去掉單則 JSON 的作答格式），數字才可比。"""
    from newssent.inference.llm_review import _SYSTEM_PROMPT

    rules, sep, _ = _SYSTEM_PROMPT.partition("\n- Answer with JSON only")
    if not sep:
        raise RuntimeError("llm_review._SYSTEM_PROMPT 的作答格式行已變更，請同步更新 judge_rules()")
    return rules


def _ids(n: int) -> list[str]:
    return [f"q{i:02d}" for i in range(1, n + 1)]


def build_prompt(items: list[tuple[str, str]]) -> str:
    lines = [f"{qid} | {target} | {headline}" for qid, (target, headline) in zip(_ids(len(items)), items)]
    return (
        f"{judge_rules()}\n\n"
        "Do not run commands, read files, or search the web; judge from the text below only.\n"
        "Label every item. Items (id | target company | headline):\n" + "\n".join(lines) + "\n"
    )


def audit_events(jsonl: str) -> list[str]:
    """回傳違規的 item 類型（工具呼叫等）；空清單＝乾淨。解析不了的行也算違規，不放過。"""
    bad: list[str] = []
    for line in jsonl.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            bad.append("unparseable-event")
            continue
        if event.get("type") == "turn.failed":
            bad.append("turn.failed")
        item_type = (event.get("item") or {}).get("type")
        if item_type and item_type not in ALLOWED_ITEM_TYPES:
            bad.append(item_type)
    return bad


def parse_batch_output(raw: str, ids: list[str]) -> dict[str, str] | None:
    """id 集合必須與題目完全一致、每個標籤合法；否則整批作廢（不猜、不補）。"""
    try:
        labels = json.loads(raw)["labels"]
        out = {str(x["id"]): str(x["label"]).strip().lower() for x in labels}
    except (json.JSONDecodeError, KeyError, TypeError):
        return None
    if len(labels) != len(ids) or set(out) != set(ids):
        return None
    if any(v not in LABEL_NAMES for v in out.values()):
        return None
    return out


def find_codex() -> str:
    for candidate in (os.environ.get("CODEX_BIN"), shutil.which("codex"), CODEX_FALLBACK_BIN):
        if candidate and Path(candidate).exists():
            return candidate
    raise SystemExit("找不到 codex：請安裝 Codex CLI，或以環境變數 CODEX_BIN 指定路徑")


def run_codex_batch(items: list[tuple[str, str]], codex_bin: str) -> dict[str, str] | None:
    """對一批 (公司名, 標題) 盲判；失敗、違規或格式不符都回 None。"""
    ids = _ids(len(items))
    with tempfile.TemporaryDirectory(prefix="judge_") as tmp:
        tmp_path = Path(tmp)
        work = tmp_path / "work"  # 空目錄：Codex 的工作根目錄
        work.mkdir()
        schema = tmp_path / "schema.json"
        schema.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        last = tmp_path / "last.json"
        cmd = [
            codex_bin, "exec", "--ephemeral", "--skip-git-repo-check", "--ignore-user-config",
            "-s", "read-only", "-C", str(work), "-m", JUDGE_MODEL,
            "-c", f'model_reasoning_effort="{JUDGE_EFFORT}"',
            "--output-schema", str(schema), "-o", str(last), "--json", "-",
        ]
        try:
            proc = subprocess.run(
                cmd, input=build_prompt(items), capture_output=True, text=True, encoding="utf-8", timeout=300
            )
        except subprocess.TimeoutExpired:
            print("    逾時")
            return None
        if proc.returncode != 0:
            print(f"    codex 結束碼 {proc.returncode}：{proc.stderr.strip()[-300:]}")
            return None
        bad = audit_events(proc.stdout)
        if bad:
            print(f"    稽核不通過（{', '.join(sorted(set(bad)))}）→ 本批作廢")
            return None
        if not last.exists():
            return None
        return parse_batch_output(last.read_text(encoding="utf-8"), ids)


# --- 計分 ---


def cohen_kappa(human: list[str], pred: list[str]) -> float:
    n = len(human)
    po = sum(h == p for h, p in zip(human, pred)) / n
    ch, cp = Counter(human), Counter(pred)
    pe = sum(ch[k] * cp[k] for k in set(ch) | set(cp)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def score(human: list[str], pred: list[str]) -> dict:
    neg = [p for h, p in zip(human, pred) if h == "negative"]
    return {
        "n": len(human),
        "agree": sum(h == p for h, p in zip(human, pred)),
        "agreement": sum(h == p for h, p in zip(human, pred)) / len(human),
        "kappa": cohen_kappa(human, pred),
        "neg_hit": sum(p == "negative" for p in neg),
        "neg_total": len(neg),
        "neg_recall": (sum(p == "negative" for p in neg) / len(neg)) if neg else 0.0,
        "missing": sum(p == MISSING for p in pred),
        "confusion": Counter(zip(human, pred)),
    }


def mcnemar(human: list[str], a: list[str], b: list[str]) -> tuple[int, int, float]:
    """配對精確檢定（雙尾二項），只看不一致格；與 compare_arms.mcnemar_p 同一算法。"""
    a_only = sum(1 for h, x, y in zip(human, a, b) if x == h and y != h)
    b_only = sum(1 for h, x, y in zip(human, a, b) if y == h and x != h)
    n = a_only + b_only
    if n == 0:
        return a_only, b_only, 1.0
    tail = sum(comb(n, i) for i in range(min(a_only, b_only) + 1)) / (2**n)
    return a_only, b_only, min(1.0, 2 * tail)


def verdict(rule: str, judge: dict, model: dict | None, p_value: float | None) -> tuple[bool, list[str]]:
    """依預先聲明的標準逐條判定；回傳 (是否合格, 逐條理由)。"""
    if rule == "strict":
        if model is None or p_value is None:
            raise ValueError("嚴格標準需要被評模型的判讀（先跑 export-preds）")
        checks = [
            (
                judge["agreement"] > model["agreement"],
                f"一致率高於 {MODEL_ARTIFACT}：{judge['agreement']:.1%} vs {model['agreement']:.1%}",
            ),
            (p_value < STRICT_ALPHA, f"McNemar p < {STRICT_ALPHA}：p = {p_value:.3f}"),
            (
                judge["neg_recall"] >= STRICT_MIN_NEG_RECALL,
                f"負面召回 ≥ {STRICT_MIN_NEG_RECALL:.0%}：{judge['neg_hit']}/{judge['neg_total']}",
            ),
        ]
    elif rule == "lenient":
        checks = [
            (judge["agreement"] >= LENIENT_MIN_AGREEMENT, f"一致率 ≥ {LENIENT_MIN_AGREEMENT:.0%}：{judge['agreement']:.1%}"),
            (judge["kappa"] >= LENIENT_MIN_KAPPA, f"κ ≥ {LENIENT_MIN_KAPPA}：{judge['kappa']:.3f}"),
        ]
    else:
        raise ValueError(f"未知的合格標準 {rule!r}")
    return all(ok for ok, _ in checks), [("✅ " if ok else "❌ ") + text for ok, text in checks]


# --- 報告 ---


def confusion_lines(cm: Counter) -> list[str]:
    cols = list(LABEL_NAMES) + ([MISSING] if any(p == MISSING for _, p in cm) else [])
    lines = ["| 人工＼裁判 | " + " | ".join(cols) + " |", "|---" * (len(cols) + 1) + "|"]
    for h in LABEL_NAMES:
        lines.append(f"| {h} | " + " | ".join(str(cm[(h, p)]) for p in cols) + " |")
    return lines


def write_report(rows, judge_preds, model_preds, stats) -> None:
    human = [r["human"] for r in rows]
    js = score(human, judge_preds)
    ms = score(human, model_preds) if model_preds else None
    a_only = b_only = p_value = None
    if model_preds:
        a_only, b_only, p_value = mcnemar(human, model_preds, judge_preds)
    passed, reasons = verdict(PASS_RULE, js, ms, p_value)

    out = [
        "# 裁判資格考：Codex 能不能當情緒標籤的裁判？",
        "",
        f"> 產出 {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC｜依 [預先聲明](judge_qualification_prereg.md) 執行｜"
        f"裁判 `{judge_key()}`｜合格標準：**{PASS_RULE}**",
        "> 考題＝財金組盲標 120 則；裁判只看 (公司名, 標題)，看不到模型判讀；有工具呼叫的批次一律作廢。",
        "",
        "## 裁決",
        "",
        f"**{'合格' if passed else '不合格'}**",
        "",
        *[f"- {x}" for x in reasons],
        "",
        "## 成績",
        "",
        "| 判讀者 | 一致率 | κ | 負面召回 | 未作答 |",
        "|---|---|---|---|---|",
        f"| 裁判 `{judge_key()}` | {js['agreement']:.1%}（{js['agree']}/{js['n']}） | {js['kappa']:.3f} | "
        f"{js['neg_hit']}/{js['neg_total']} | {js['missing']} |",
    ]
    if ms:
        out.append(
            f"| 被評模型 `{MODEL_ARTIFACT}` | {ms['agreement']:.1%}（{ms['agree']}/{ms['n']}） | {ms['kappa']:.3f} | "
            f"{ms['neg_hit']}/{ms['neg_total']} | — |"
        )
        out += ["", f"McNemar（雙尾）：只有模型對 {a_only} 則、只有裁判對 {b_only} 則，p = {p_value:.3f}"]

    out += ["", "## 分批一致率", "", "| 批次 | 題數 | 裁判 | 被評模型 |", "|---|---|---|---|"]
    for batch in dict.fromkeys(r["batch"] for r in rows):
        idx = [i for i, r in enumerate(rows) if r["batch"] == batch]
        j = sum(judge_preds[i] == human[i] for i in idx) / len(idx)
        m = f"{sum(model_preds[i] == human[i] for i in idx) / len(idx):.1%}" if model_preds else "—"
        out.append(f"| {batch} | {len(idx)} | {j:.1%} | {m} |")

    out += ["", "## 裁判混淆矩陣（列＝財金組、欄＝裁判）", "", *confusion_lines(js["confusion"])]
    out += [
        "",
        "## 執行紀錄",
        "",
        f"- Codex 呼叫 {stats['calls']} 次（{stats['codex_version'] or '全部沿用快取'}），"
        f"每批 {BATCH_SIZE} 則，打亂種子 {SHUFFLE_SEED}",
        f"- 稽核或格式不符而作廢重試的批次：{stats['rejected']}",
        f"- 本次新判 {stats['new']} 則、沿用快取 {stats['cached']} 則；逐則判讀見 `docs/{CACHE_CSV.name}`",
    ]
    REPORT_MD.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"\n裁決：{'合格' if passed else '不合格'}")
    for x in reasons:
        print(f"  {x}")
    print(f"報告：{REPORT_MD}")


# --- 子命令 ---


def assert_preregistered() -> None:
    """合格標準必須已選定，且預先聲明與本檔都已 commit、無未提交變更——防止看完成績再改規則。"""
    if PASS_RULE not in ("strict", "lenient"):
        raise SystemExit("合格標準尚未選定：先在預先聲明與本檔的 PASS_RULE 寫死 strict 或 lenient，並 commit")
    for path in (PREREG_MD, Path(__file__).resolve()):
        git = ["git", "-C", str(BACKEND_ROOT)]
        tracked = subprocess.run([*git, "ls-files", "--error-unmatch", str(path)], capture_output=True).returncode == 0
        dirty = subprocess.run([*git, "status", "--porcelain", "--", str(path)], capture_output=True, text=True)
        if not tracked or dirty.stdout.strip():
            raise SystemExit(f"{path.name} 尚未 commit（或有未提交的修改）；預先聲明必須在考試前定稿")


def cmd_smoke() -> int:
    codex_bin = find_codex()
    t0 = time.perf_counter()
    labels = run_codex_batch(SMOKE_ITEMS, codex_bin)
    print(f"耗時 {time.perf_counter() - t0:.1f}s")
    if labels is None:
        print("試跑失敗")
        return 1
    for qid, (target, headline) in zip(_ids(len(SMOKE_ITEMS)), SMOKE_ITEMS):
        print(f"  {labels[qid]:<8} {target}: {headline}")
    return 0


def cmd_export_preds() -> int:
    from newssent.ml import registry
    from newssent.text.preprocess import build_target_text

    rows = load_exam_rows()
    model, metadata = registry.load(MODEL_ARTIFACT)
    if not metadata.get("target_dependent"):
        raise SystemExit(f"{MODEL_ARTIFACT} 不是目標導向模型，與 production 推論路徑不符")
    preds = model.predict([build_target_text(company_name(r["ticker"]), r["title"]) for r in rows])
    with open(PREDS_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "title", "artifact", "trained_commit", "model_label"])
        writer.writeheader()
        for r, p in zip(rows, preds):
            writer.writerow(
                {
                    "ticker": r["ticker"],
                    "title": r["title"],
                    "artifact": MODEL_ARTIFACT,
                    "trained_commit": metadata.get("git_commit", ""),
                    "model_label": LABEL_NAMES[int(p)],
                }
            )
    print(f"已匯出 {len(rows)} 則 {MODEL_ARTIFACT} 判讀 → {PREDS_CSV}")
    return 0


def cmd_run() -> int:
    assert_preregistered()
    rows = load_exam_rows()
    model_map = load_model_preds()
    if PASS_RULE == "strict" and any((r["ticker"], r["title"]) not in model_map for r in rows):
        raise SystemExit(f"嚴格標準需要 {MODEL_ARTIFACT} 對全部考題的判讀：先在 GPU 機跑 export-preds")

    cache = load_cache()
    todo = [r for r in rows if (r["ticker"], r["title"]) not in cache]
    random.Random(SHUFFLE_SEED).shuffle(todo)
    codex_bin = find_codex() if todo else ""
    version = subprocess.run([codex_bin, "--version"], capture_output=True, text=True).stdout.strip() if todo else ""
    stats = {"calls": 0, "rejected": 0, "new": 0, "cached": len(rows) - len(todo), "codex_version": version}

    for start in range(0, len(todo), BATCH_SIZE):
        batch = todo[start : start + BATCH_SIZE]
        batch_id = f"b{start // BATCH_SIZE + 1:02d}"
        items = [(company_name(r["ticker"]), r["title"]) for r in batch]
        for attempt in range(1, MAX_ATTEMPTS + 1):
            print(f"  批次 {batch_id}（{len(batch)} 則）第 {attempt} 次…")
            stats["calls"] += 1
            labels = run_codex_batch(items, codex_bin)
            if labels is not None:
                append_cache(batch, labels, batch_id)
                stats["new"] += len(batch)
                break
            stats["rejected"] += 1

    cache = load_cache()
    judge_preds = [cache.get((r["ticker"], r["title"]), MISSING) for r in rows]
    model_preds = [model_map[(r["ticker"], r["title"])] for r in rows] if model_map else None
    write_report(rows, judge_preds, model_preds, stats)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="裁判資格考（依預先聲明執行）")
    parser.add_argument("command", choices=["smoke", "export-preds", "run"])
    args = parser.parse_args()
    return {"smoke": cmd_smoke, "export-preds": cmd_export_preds, "run": cmd_run}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
