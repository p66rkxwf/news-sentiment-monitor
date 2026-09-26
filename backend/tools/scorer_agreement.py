"""換評分器的一致性檢驗：雲端託管模型（ALERT_SCORER）vs 本機 gemma3:27b（ALERT_SCORER_LEGACY）。

用法（backend/ 目錄執行）:
    python tools/scorer_agreement.py --out ../agreement

門檻事先寫在 docs/scorer_switch_prereg.md（先 commit、再跑）；本工具只計算並套用門檻，不調門檻。

三個層次：
1. 逐則標題：同一 (ticker, 標題) 兩個評分器都評過者。標籤＝機率最大的類別（LLM 評分是 one-hot）。
   原始一致率（Wilson 95% CI）、Cohen's κ、3×3 混淆矩陣、舊評分器判負面者被新評分器判負面的比例
   （預警只看負向偏離，負面抓不到的代價最高）。
2. 每日分數：同一 (ticker, 交易日) 兩者都有分數者的 Spearman 相關——看板實際用的是每日分數的 z 值。
3. 覆蓋率：舊評分器評過、發布時間落在新評分器評分範圍內的標題，新評分器也評到的比例
   （缺的＝解析失敗或尚未回補）。覆蓋率不足時不下結論。
盤勢報導標題（config.ALERT_PRICE_REPORT_PATTERNS）與看板一致，一律排除。
"""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from newssent.config import (  # noqa: E402
    ALERT_SCORE_DB_PATH,
    ALERT_SCORER,
    ALERT_SCORER_LEGACY,
    LABEL_NAMES,
)
from newssent.inference.alerts import daily_scores, headline_score, is_price_report  # noqa: E402

# --- 預先聲明的門檻（docs/scorer_switch_prereg.md）；改動必須先改該文件並 commit ---
KAPPA_ADOPT = 0.60
KAPPA_DISCLOSE = 0.40
MIN_COVERAGE = 0.95
MIN_PAIRS = 200


def _label(neg: float, neu: float, pos: float) -> str:
    probs = (neg, neu, pos)
    return LABEL_NAMES[max(range(3), key=probs.__getitem__)]


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (math.nan, math.nan)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def cohen_kappa(pairs: list[tuple[str, str]]) -> float:
    n = len(pairs)
    if n == 0:
        return math.nan
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[label] * cb[label] for label in LABEL_NAMES) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else math.nan


def spearman(xs: list[float], ys: list[float]) -> float:
    from scipy.stats import spearmanr

    return float(spearmanr(xs, ys).statistic) if len(xs) >= 3 else math.nan


def verdict(kappa: float, coverage: float, n_pairs: int) -> str:
    if n_pairs < MIN_PAIRS:
        return f"不下結論：成對樣本 {n_pairs} < {MIN_PAIRS}"
    if coverage < MIN_COVERAGE:
        return f"不下結論：覆蓋率 {coverage:.1%} < {MIN_COVERAGE:.0%}（先補齊回補或查解析失敗）"
    if kappa >= KAPPA_ADOPT:
        return "採用"
    if kappa >= KAPPA_DISCLOSE:
        return "採用，但須揭露：本機評分器的回測結論不適用於新評分器"
    return "暫停採用：先查提示詞與解析，或改試下一個候選模型"


def run(db_path: Path, new: str, legacy: str) -> dict:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    rows = conn.execute(
        """
        SELECT a.ticker, a.title, h.published_at,
               a.p_negative, a.p_neutral, a.p_positive,
               b.p_negative, b.p_neutral, b.p_positive
        FROM headline_scores a
        JOIN headline_scores b ON b.ticker = a.ticker AND b.title = a.title AND b.scorer = ?
        JOIN headlines h ON h.ticker = a.ticker AND h.title = a.title
        WHERE a.scorer = ?
        """,
        (legacy, new),
    ).fetchall()
    rows = [r for r in rows if not is_price_report(r[1])]

    first_new = conn.execute(
        "SELECT MIN(h.published_at) FROM headline_scores s JOIN headlines h ON h.ticker = s.ticker AND h.title = s.title "
        "WHERE s.scorer = ?",
        (new,),
    ).fetchone()[0]
    legacy_in_window = [
        t for (t,) in conn.execute(
            "SELECT h.title FROM headline_scores s JOIN headlines h ON h.ticker = s.ticker AND h.title = s.title "
            "WHERE s.scorer = ? AND h.published_at >= ?",
            (legacy, first_new or "9999"),
        )
        if not is_price_report(t)
    ]
    coverage = len(rows) / len(legacy_in_window) if legacy_in_window else 0.0

    labels = [(_label(*r[6:9]), _label(*r[3:6])) for r in rows]  # (舊, 新)
    agree = sum(a == b for a, b in labels)
    confusion = Counter(labels)
    legacy_neg = [b for a, b in labels if a == "negative"]

    # 每日分數：各 ticker 以兩者都評過的標題聚合（同一批標題，差異只來自評分器）
    sessions = [datetime.fromisoformat(s).date() for (s,) in conn.execute(
        "SELECT session FROM trading_sessions ORDER BY session")]
    by_ticker: dict[str, list[tuple]] = defaultdict(list)
    for r in rows:
        by_ticker[r[0]].append(r)
    xs, ys = [], []
    for ticker_rows in by_ticker.values():
        stamp = [datetime.fromisoformat(r[2]) for r in ticker_rows]
        old_daily = daily_scores(((t, headline_score(r[6], r[8])) for t, r in zip(stamp, ticker_rows)), sessions)
        new_daily = daily_scores(((t, headline_score(r[3], r[5])) for t, r in zip(stamp, ticker_rows)), sessions)
        for o, n in zip(old_daily, new_daily):
            if o.score is not None and n.score is not None:
                xs.append(o.score)
                ys.append(n.score)
    conn.close()

    kappa = cohen_kappa(labels)
    return {
        "new": new,
        "legacy": legacy,
        "pairs": len(rows),
        "agree": agree,
        "agree_ci": wilson(agree, len(rows)),
        "kappa": kappa,
        "confusion": confusion,
        "neg_recall": (sum(b == "negative" for b in legacy_neg), len(legacy_neg)),
        "daily_pairs": len(xs),
        "daily_spearman": spearman(xs, ys),
        "coverage": coverage,
        "legacy_in_window": len(legacy_in_window),
        "first_new": first_new,
        "verdict": verdict(kappa, coverage, len(rows)),
        "disagreements": [(r[0], r[2], r[1], a, b) for r, (a, b) in zip(rows, labels) if a != b],
    }


def render(res: dict) -> str:
    n = res["pairs"]
    lo, hi = res["agree_ci"]
    k, m = res["neg_recall"]
    lines = [
        "# 評分器換用一致性報告",
        "",
        f"> 產出 {datetime.now().astimezone().isoformat(timespec='minutes')}｜新 `{res['new']}` vs 舊 `{res['legacy']}`"
        f"｜門檻見 docs/scorer_switch_prereg.md",
        "",
        f"**判定：{res['verdict']}**",
        "",
        "| 指標 | 數值 |",
        "|---|---|",
        f"| 成對標題數 | {n} |",
        f"| 覆蓋率（新評分器評到的比例） | {res['coverage']:.1%}（{n}/{res['legacy_in_window']}，自 {res['first_new']}） |",
        f"| 原始一致率 | {res['agree'] / n:.1%}（95% CI {lo:.1%}–{hi:.1%}） |" if n else "| 原始一致率 | — |",
        f"| Cohen's κ | {res['kappa']:.3f} |",
        f"| 舊判負面 → 新也判負面 | {k}/{m}（{k / m:.1%}） |" if m else "| 舊判負面 → 新也判負面 | — |",
        f"| 每日分數 Spearman（{res['daily_pairs']} 個 ticker×交易日） | {res['daily_spearman']:.3f} |",
        "",
        "## 混淆矩陣（列＝舊、欄＝新）",
        "",
        "| 舊＼新 | " + " | ".join(LABEL_NAMES) + " |",
        "|---|" + "---|" * len(LABEL_NAMES),
    ]
    for a in LABEL_NAMES:
        lines.append(f"| {a} | " + " | ".join(str(res["confusion"].get((a, b), 0)) for b in LABEL_NAMES) + " |")
    lines += ["", f"不一致的 {len(res['disagreements'])} 則逐則列在 disagreements.csv。", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="新舊評分器一致性檢驗")
    parser.add_argument("--out", type=Path, required=True, help="輸出目錄（report.md、disagreements.csv）")
    parser.add_argument("--db", type=Path, default=ALERT_SCORE_DB_PATH)
    parser.add_argument("--new", default=ALERT_SCORER)
    parser.add_argument("--legacy", default=ALERT_SCORER_LEGACY)
    args = parser.parse_args(argv)

    res = run(args.db, args.new, args.legacy)
    args.out.mkdir(parents=True, exist_ok=True)
    report = render(res)
    (args.out / "report.md").write_text(report, encoding="utf-8")
    with (args.out / "disagreements.csv").open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ticker", "published_at", "title", "legacy", "new"])
        w.writerows(res["disagreements"])
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
