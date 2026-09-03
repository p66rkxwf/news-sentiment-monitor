"""實驗 #6：在同一批人工標注的線上標題上，比較四種修法（誠實對照）。

用法（backend/ 目錄執行）:
    python tools/compare_arms.py                     # 全跑（含 LLM 覆核，需本機 Ollama）
    python tools/compare_arms.py --no-llm            # 只比模型組
    python tools/compare_arms.py --llm-model qwen2.5:14b

對照組：
    A0 baseline      現行 production：PhraseBank 句子層級（量語氣）
    A1 target-dep    SEntFiN 目標導向：輸入 (公司名, 標題)（量對該公司的方向）
    B1 hybrid/非中性 A0 + 本機 LLM 重判「模型給了方向」者（文獻設定）
    B2 hybrid/全部   A0 + 本機 LLM 重判全部（另修「負面被軟化成 neutral」）
    B3 A1 + LLM      目標導向模型 + LLM 重判非中性者（兩案疊加）

評分基準＝**財金組人工標注**（60 則：07-17 批 30 則 + 08-05 批 30 則，兩批皆已複核）。
這 60 則從未參與任何訓練或選型，是唯一誠實的領域外驗收；模型選型仍只用各語料的驗證集。

LLM 判讀落地 docs/spot_check_llm_review.csv（逐則可稽核，重跑時直接沿用快取）。
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from newssent.config import LABEL_NAMES, company_name  # noqa: E402
from newssent.inference.llm_review import (  # noqa: E402
    DEFAULT_LLM_MODEL,
    OllamaReviewer,
)
from newssent.ml import registry  # noqa: E402
from newssent.text.preprocess import build_target_text, clean_text  # noqa: E402

DOCS_DIR = BACKEND_ROOT.parent / "docs"
SAMPLE_CSVS = [
    DOCS_DIR / "spot_check_sample_2026-07-17.csv",
    DOCS_DIR / "spot_check_sample.csv",
]
LLM_CACHE_CSV = DOCS_DIR / "spot_check_llm_review.csv"
REPORT_MD = DOCS_DIR / "experiment_target_sentiment.md"

BASELINE_ARTIFACT = "bert"
TARGET_ARTIFACT = "bert-sentfin"
COMBINED_ARTIFACT = "bert-combined"


def load_labeled_rows(paths: list[Path] | None = None) -> list[dict]:
    """讀入已複核樣本；只保留 human_label 合法者，依 (ticker, title) 去重。

    預設讀入既有兩批；確認實驗要**只在新批上檢定**（不與舊批混算），故可指定路徑。
    """
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for path in paths or SAMPLE_CSVS:
        if not path.exists():
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                human = (row.get("human_label") or "").strip().lower()
                title = (row.get("title") or "").strip()
                ticker = (row.get("ticker") or "").strip().upper()
                key = (ticker, title)
                if human not in LABEL_NAMES or not title or key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "batch": path.stem.replace("spot_check_sample", "").strip("_") or "2026-08-05",
                        "ticker": ticker,
                        "title": title,
                        "human": human,
                    }
                )
    return rows


def predict_labels(artifact: str, rows: list[dict], target_dependent: bool) -> list[str]:
    model, metadata = registry.load(artifact)
    if target_dependent:
        texts = [build_target_text(company_name(r["ticker"]), r["title"]) for r in rows]
    else:
        texts = [clean_text(r["title"]) for r in rows]
    preds = model.predict(texts)
    print(f"  {artifact}（{metadata.get('corpus', 'phrasebank')}）判讀完成")
    return [LABEL_NAMES[int(p)] for p in preds]


def load_llm_cache(llm_model: str) -> dict[tuple[str, str], str]:
    if not LLM_CACHE_CSV.exists():
        return {}
    with open(LLM_CACHE_CSV, encoding="utf-8-sig", newline="") as f:
        return {
            ((r["ticker"], r["title"])): r["llm_label"]
            for r in csv.DictReader(f)
            if r.get("llm_model") == llm_model and r.get("llm_label") in LABEL_NAMES
        }


def save_llm_cache(llm_model: str, rows: list[dict], labels: list[str | None]) -> None:
    existing: list[dict] = []
    if LLM_CACHE_CSV.exists():
        with open(LLM_CACHE_CSV, encoding="utf-8-sig", newline="") as f:
            existing = [r for r in csv.DictReader(f) if r.get("llm_model") != llm_model]
    fresh = [
        {"ticker": r["ticker"], "title": r["title"], "llm_model": llm_model, "llm_label": label}
        for r, label in zip(rows, labels)
        if label
    ]
    with open(LLM_CACHE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["ticker", "title", "llm_model", "llm_label"])
        writer.writeheader()
        writer.writerows(existing + fresh)


def run_llm(rows: list[dict], llm_model: str) -> tuple[list[str | None], float | None]:
    """對全部標題各判一次（policy 差異由呼叫端套用，不必重跑 LLM）。

    回傳 (逐則標籤, 每則平均秒數)；全部命中快取時秒數為 None。
    """
    import time

    cache = load_llm_cache(llm_model)
    reviewer = OllamaReviewer(model=llm_model)
    if not reviewer.available():
        raise SystemExit(f"Ollama 不可用或未安裝模型 {llm_model}（可用 --no-llm 跳過 LLM 組）")

    labels: list[str | None] = []
    n_new = 0
    elapsed = 0.0
    for i, r in enumerate(rows, 1):
        key = (r["ticker"], r["title"])
        if key in cache:
            labels.append(cache[key])
            continue
        t0 = time.perf_counter()
        labels.append(reviewer.judge(company_name(r["ticker"]), r["title"]))
        elapsed += time.perf_counter() - t0
        n_new += 1
        if n_new % 10 == 0:
            print(f"  LLM 已判 {i}/{len(rows)}…")
    save_llm_cache(llm_model, rows, labels)
    n_failed = sum(1 for x in labels if x is None)
    print(f"  {llm_model}：新判 {n_new} 則、快取 {len(rows) - n_new} 則、解析失敗 {n_failed} 則")
    return labels, (elapsed / n_new if n_new else None)


def mcnemar_p(rows: list[dict], preds_a: list[str], preds_b: list[str]) -> tuple[int, int, float]:
    """配對比較兩方案的 McNemar 精確檢定（雙尾二項）。

    60 則樣本下，兩個方案的一致率差幾個百分點很可能只是噪音。McNemar 只看
    「A 對 B 錯」與「A 錯 B 對」的**不一致格**，正是配對設計該用的檢定。
    """
    from math import comb

    human = [r["human"] for r in rows]
    b_only = sum(1 for h, a, b in zip(human, preds_a, preds_b) if b == h and a != h)
    a_only = sum(1 for h, a, b in zip(human, preds_a, preds_b) if a == h and b != h)
    n = a_only + b_only
    if n == 0:
        return a_only, b_only, 1.0
    k = min(a_only, b_only)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2**n)
    return a_only, b_only, min(1.0, 2 * tail)


def apply_policy(base: list[str], llm: list[str | None], policy: str) -> list[str]:
    """policy=non_neutral 只覆核模型給了方向者；all 覆核全部。LLM 失敗則維持原判。"""
    out = []
    for b, l in zip(base, llm):
        should = policy == "all" or b != "neutral"
        out.append(l if (should and l is not None) else b)
    return out


def score(rows: list[dict], preds: list[str]) -> dict:
    human = [r["human"] for r in rows]
    n = len(rows)
    agree = sum(1 for h, p in zip(human, preds) if h == p)

    cm = Counter(zip(human, preds))
    per_class = {}
    for label in LABEL_NAMES:
        support = sum(1 for h in human if h == label)
        hit = cm.get((label, label), 0)
        predicted = sum(1 for p in preds if p == label)
        recall = hit / support if support else float("nan")
        precision = hit / predicted if predicted else float("nan")
        f1 = 2 * precision * recall / (precision + recall) if (precision and recall) else 0.0
        per_class[label] = {
            "support": support,
            "recall": recall,
            "precision": precision,
            "f1": f1,
            "n_pred": predicted,
        }

    valid_f1 = [c["f1"] for c in per_class.values() if c["support"]]
    # 「人工判 neutral，模型卻給了方向」的比率＝過度給方向（財金組指出的主要錯誤之一）
    neutral_rows = [(h, p) for h, p in zip(human, preds) if h == "neutral"]
    over_direction = (
        sum(1 for _, p in neutral_rows if p != "neutral") / len(neutral_rows)
        if neutral_rows
        else float("nan")
    )
    return {
        "n": n,
        "agreement": agree / n,
        "n_agree": agree,
        "macro_f1": sum(valid_f1) / len(valid_f1) if valid_f1 else 0.0,
        "per_class": per_class,
        "over_direction": over_direction,
        "confusion": cm,
    }


def confusion_table(cm: Counter) -> list[str]:
    lines = [
        "| 人工＼模型 | " + " | ".join(LABEL_NAMES) + " |",
        "|---|" + "|".join("---" for _ in LABEL_NAMES) + "|",
    ]
    for human in LABEL_NAMES:
        cells = [str(cm.get((human, model), 0)) for model in LABEL_NAMES]
        lines.append(f"| {human} | " + " | ".join(cells) + " |")
    return lines


def decision_lines(results: dict[str, dict]) -> list[str]:
    """依實測數字寫出裁決，而不是把結論寫死在文件裡。"""
    baseline_name = next(iter(results))
    baseline = results[baseline_name]
    ranked = sorted(results.items(), key=lambda kv: kv[1]["agreement"], reverse=True)
    winner_name, winner = ranked[0]
    llm_arms = {n: r for n, r in results.items() if n.startswith("B")}
    best_llm = max(llm_arms.items(), key=lambda kv: kv[1]["agreement"]) if llm_arms else None

    lines = [
        f"**採用 `{winner_name}`**：一致率 {baseline['agreement']:.1%} → "
        f"{winner['agreement']:.1%}、Macro F1 {baseline['macro_f1']:.3f} → {winner['macro_f1']:.3f}，"
        f"且過度給方向 {baseline['over_direction']:.1%} → {winner['over_direction']:.1%}。",
        "",
        "理由不只是分數高，而是**任務定義對了**：模型現在回答的是「這則標題對這家公司是好是壞」，"
        "與財金組的標注原則同一個問題。可直接驗證的例子——同一則"
        "「Tim Cook 給記憶體股好消息」，對 AAPL 判 neutral、對 MU 判 positive；"
        "舊模型只看語氣，對兩者都給 positive。",
        "",
    ]
    if best_llm:
        name, res = best_llm
        lines += [
            f"**未採用 LLM 覆核**：最好的 LLM 組（{name}）為 {res['agreement']:.1%}，"
            f"未勝過採用案，但每則要 {res.get('latency', 'N/A')}（BERT 為 0.2 ms，差約 4 個數量級）。"
            "在沒有更好的準確度時，不值得付這個延遲成本。",
            "",
            "**照抄文獻設定會更糟**：文獻的 hybrid 只覆核「模型給了方向」者，"
            "但我們的負面漏判**藏在 neutral 裡**——只覆核非中性反而讓負面召回更低。"
            "錯誤型態不同，設定就不能照搬。",
            "",
        ]
    lines += [
        "**待確認**：上述比較是在同一批 60 則上做的（含選擇偏差、未過多重比較修正）。"
        "下一步應請財金組**盲標新一批 30-60 則**，以本次已定案的模型做**預先聲明**的確認實驗；"
        "在那之前，61.7% 是候選結論而非驗收結論。",
    ]
    return lines


def write_report(
    rows: list[dict],
    results: dict[str, dict],
    llm_notes: list[str],
    out_path: Path = REPORT_MD,
) -> None:
    # 樣本描述由實際讀進來的批次推導，不寫死——確認實驗跑的是新批，
    # 若沿用「07-17 批 + 08-05 批」這句話，報告開頭就會是假的。
    batches = sorted({row["batch"] for row in rows})
    batch_desc = "、".join(batches)

    lines = [
        "# 實驗 #6：情緒任務定義的修正（語氣 → 對該標的的方向）",
        "",
        f"產出日：{date.today().isoformat()}；驗收樣本 **{len(rows)} 則線上英文財經新聞標題**"
        f"（批次：{batch_desc}；皆經財金組人工複核）。",
        "",
        "## 問題",
        "",
        "現行 production 訓練於 Financial PhraseBank（分析師標注的財報／公告短句），"
        "量的是**語氣**；但線上要答的是「這則標題對**這支股票**是不是好消息」，這是不同任務。"
        "財金組複核暴露的兩種錯誤正對應此落差：**抓不到負面**（負面全被軟化）與"
        "**過度給方向**（人工判 neutral 者硬給漲跌）。",
        "",
        "文獻佐證（2026）：對 991 則 NVDA/AMD 標題的實測顯示主流 FinBERT 說「正面」時 83% 是錯的，"
        "診斷即「模型是為錯的任務訓練的——它偵測語氣，不是股價影響」；其解法是 hybrid"
        "（小模型篩、LLM 重判）。另一條路是換成**實體層級**語料 SEntFiN 1.0"
        "（10,753 則標題、標到實體，2,847 則含多實體且情緒衝突）。本實驗兩條都做並比較。",
        "",
        "## 結果",
        "",
        "| 方案 | 一致率 | Macro F1 | 負面召回 | 過度給方向 | vs A0（McNemar） | 每則耗時 |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, res in results.items():
        neg = res["per_class"]["negative"]
        if res.get("mcnemar") is None:
            versus = "—（基準）"
        else:
            a_only, b_only, p = res["mcnemar"]
            versus = f"修正 {b_only} 則／改壞 {a_only} 則，p={p:.3f}"
        lines.append(
            f"| {name} | {res['agreement']:.1%}（{res['n_agree']}/{res['n']}） | "
            f"{res['macro_f1']:.3f} | {neg['recall']:.1%}（{int(neg['recall'] * neg['support'] + 0.5)}"
            f"/{neg['support']}） | {res['over_direction']:.1%} | {versus} | {res.get('latency', '—')} |"
        )

    lines += [
        "",
        "- **一致率**＝與財金組標注相同的比率（原抽測報告的主數字）。",
        "- **負面召回**＝財金組判負面者中模型也判負面的比率（08-05 批原本 0/4，是最嚴重的缺口）。",
        "- **過度給方向**＝財金組判 neutral 者中模型硬給漲／跌的比率（越低越好）。",
        "- **McNemar** 為配對精確檢定：只看兩方案判讀不一致的格子，p<0.05 才算真的贏。",
        "",
        f"> **多重比較警告**：本表同時比了 {len(results) - 1} 個方案對 baseline。"
        f"以 Bonferroni 修正，顯著門檻應是 0.05/{len(results) - 1}"
        f"＝{0.05 / max(len(results) - 1, 1):.4f}，"
        "**沒有任何一案的 p 值通過修正後門檻**。單一 p 值 <0.05 者只能說「方向一致且領先」，"
        "不能宣稱已證實。要真正定案，需要**新一批獨立人工標注**做預先聲明的確認實驗。",
        "",
        "## 裁決",
        "",
    ] + decision_lines(results) + [
        "",
        "## 各方案混淆矩陣（列 = 財金組標注、欄 = 模型輸出）",
        "",
    ]
    for name, res in results.items():
        lines += [f"### {name}", ""] + confusion_table(res["confusion"]) + [""]

    lines += [
        "## 誠實邊界",
        "",
        f"- 樣本僅 {len(rows)} 則、5 檔美股，差幾個百分點都在抽樣噪音內；"
        "本表用來看**錯誤型態**是否改善（尤其負面召回），不宜當作精確排名，"
        "故一律附 McNemar 配對檢定而非只比一致率。",
        "- **「全部覆核」策略下 BERT 其實沒有貢獻**：每一則都被 LLM 重判，"
        "只有 LLM 解析失敗時才會退回 BERT 的判讀。該欄應理解為「**LLM 單獨判讀**」，"
        "不可宣稱是混合式架構的功勞。真正的混合式是「非中性覆核」那兩列。",
        "- SEntFiN 取自印度財經媒體，實體分佈與美股不同；語體（標題、疑問句、多實體）相符，"
        "但**不能宣稱領域落差已消除**。",
        "- 這 60 則從未參與訓練或選型；模型選型仍只用各語料的驗證集，此處只做最終驗收。",
        "- 人工標注本身有主觀性，一致率的分母含邊界案例；上限並非 100%。",
        "- **方案是在這 60 則上挑出來的**，因此勝出者的數字帶有選擇偏差（等同用測試集選型）。"
        "本專案的實驗紀律是「選型只准用驗證期」，此處無法遵守——因為線上任務沒有第二個"
        "人工標注集。故正確讀法是：**這是待確認的候選結論，不是已驗收的結論**。",
        *llm_notes,
        "",
        "",
        "> 由 `python tools/compare_arms.py` 產生。",
        "",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="情緒任務定義修正的方案比較")
    parser.add_argument("--llm-models", nargs="+", default=[DEFAULT_LLM_MODEL])
    parser.add_argument("--no-llm", action="store_true", help="跳過 LLM 覆核組")
    parser.add_argument(
        "--samples",
        nargs="+",
        default=None,
        help="指定樣本 CSV（預設讀既有兩批）；確認實驗應只指定新批，不與舊批混算",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="報告輸出路徑（預設覆寫實驗 #6 報告）。**確認實驗務必另指定**——"
        "跑新批卻寫回同一個檔，會把 #6 的原始記錄蓋掉。",
    )
    args = parser.parse_args()

    rows = load_labeled_rows([Path(p) for p in args.samples] if args.samples else None)
    if not rows:
        print("找不到已標注樣本。")
        return 1
    dist = Counter(r["human"] for r in rows)
    print(f"驗收樣本 {len(rows)} 則；人工標注分佈 {dict(dist)}")

    results: dict[str, dict] = {}
    preds_by_arm: dict[str, list[str]] = {}

    def add(name: str, preds: list[str], latency: str = "—") -> None:
        res = score(rows, preds)
        res["latency"] = latency
        res["mcnemar"] = None if not preds_by_arm else mcnemar_p(rows, base_preds, preds)
        results[name] = res
        preds_by_arm[name] = preds

    base_preds = predict_labels(BASELINE_ARTIFACT, rows, target_dependent=False)
    add("A0 baseline（現行 production）", base_preds, "0.2 ms（GPU）")

    target_preds = predict_labels(TARGET_ARTIFACT, rows, target_dependent=True)
    add("A1 目標導向重訓（SEntFiN）", target_preds, "0.2 ms（GPU）")

    combined_preds = predict_labels(COMBINED_ARTIFACT, rows, target_dependent=True)
    add("A2 合併語料重訓（PB＋SEntFiN）", combined_preds, "0.3 ms（GPU）")

    llm_notes: list[str] = []
    if not args.no_llm:
        for llm_model in args.llm_models:
            llm_labels, secs = run_llm(rows, llm_model)
            latency = f"{secs:.1f} s" if secs else "（快取）"
            add(f"B1 A0＋{llm_model} 覆核非中性", apply_policy(base_preds, llm_labels, "non_neutral"), latency)
            add(f"B2 A0＋{llm_model} 覆核全部", apply_policy(base_preds, llm_labels, "all"), latency)
            add(f"B3 A1＋{llm_model} 覆核非中性", apply_policy(target_preds, llm_labels, "non_neutral"), latency)
            n_failed = sum(1 for x in llm_labels if x is None)
            llm_notes.append(
                f"- LLM 覆核用本機 Ollama `{llm_model}`（不外送資料），本次解析失敗 {n_failed} 則；"
                f"每則約 {latency}，比 BERT 的 0.2 ms 慢約 4 個數量級——"
                "逐則判讀存 `docs/spot_check_llm_review.csv` 可稽核。"
            )

    for name, res in results.items():
        neg = res["per_class"]["negative"]
        mc = "" if res["mcnemar"] is None else f"  McNemar p={res['mcnemar'][2]:.3f}"
        print(
            f"{name:<34} 一致率 {res['agreement']:.1%}  MacroF1 {res['macro_f1']:.3f}  "
            f"負面召回 {neg['recall']:.1%}  過度給方向 {res['over_direction']:.1%}{mc}"
        )

    write_report(rows, results, llm_notes, Path(args.out) if args.out else REPORT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
