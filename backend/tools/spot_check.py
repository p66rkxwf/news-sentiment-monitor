"""線上標題人工抽測（PLAN.md Phase 7）：PhraseBank 與實際新聞標題存在分佈落差，
以 30 則線上標題人工標注 vs 模型輸出的一致率，誠實量化這個落差。

用法（backend/ 目錄執行）:
    # 步驟 1：抓取線上標題 + 模型判讀，輸出待標注 CSV（human_label 欄留空）
    python tools/spot_check.py sample --tickers AAPL TSLA NVDA MSFT GOOG --per-ticker 6

    # 步驟 2：人工在 CSV 的 human_label 欄填 negative/neutral/positive 後
    python tools/spot_check.py report

輸出：
    docs/spot_check_sample.csv   待標注/已標注樣本
    docs/online_spot_check.md    一致率、混淆矩陣與限制討論（report 子命令）
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

from newssent.config import (  # noqa: E402
    LABEL_NAMES,
    NEWS_CACHE_BUCKET_SECONDS,
    PRODUCTION_MODEL,
)
from newssent.data.cache import NewsCache  # noqa: E402
from newssent.data.provider import YFinanceNewsProvider  # noqa: E402
from newssent.inference.analyzer import Analyzer  # noqa: E402

DOCS_DIR = BACKEND_ROOT.parent / "docs"
SAMPLE_CSV = DOCS_DIR / "spot_check_sample.csv"
REPORT_MD = DOCS_DIR / "online_spot_check.md"
FIELDS = ["ticker", "published_at", "title", "model_label", "confidence", "human_label"]


def cmd_sample(tickers: list[str], per_ticker: int) -> int:
    cache = NewsCache(BACKEND_ROOT / "news_cache.db")
    provider = YFinanceNewsProvider(cache=cache, bucket_seconds=NEWS_CACHE_BUCKET_SECONDS)
    analyzer = Analyzer.from_registry(PRODUCTION_MODEL)
    print(f"模型：{analyzer.version}")

    rows: list[dict] = []
    seen_titles: set[str] = set()
    for ticker in tickers:
        try:
            result = provider.get_news(ticker, limit=per_ticker * 2)
        except Exception as exc:
            print(f"[略過] {ticker}: {exc}")
            continue
        classified = analyzer.classify(result.articles)
        n = 0
        for c in classified:
            if c.article.title in seen_titles or n >= per_ticker:
                continue
            seen_titles.add(c.article.title)
            rows.append(
                {
                    "ticker": ticker,
                    "published_at": c.article.published_at[:10],
                    "title": c.article.title,
                    "model_label": c.label,
                    "confidence": round(c.confidence, 3),
                    "human_label": "",
                }
            )
            n += 1
        print(f"  {ticker}: 取 {n} 則")

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SAMPLE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"共 {len(rows)} 則，已輸出 {SAMPLE_CSV}")
    print("請在 human_label 欄填入 negative/neutral/positive 後執行 report 子命令。")
    return 0


def cmd_report() -> int:
    if not SAMPLE_CSV.exists():
        print(f"找不到 {SAMPLE_CSV}，請先執行 sample 子命令。")
        return 1
    with open(SAMPLE_CSV, encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f)]

    labeled = [r for r in rows if (r.get("human_label") or "").strip() in LABEL_NAMES]
    if not labeled:
        print("human_label 欄尚未標注（需為 negative/neutral/positive）。")
        return 1

    n_agree = sum(1 for r in labeled if r["model_label"] == r["human_label"].strip())
    agreement = n_agree / len(labeled)

    # 混淆矩陣：列 = 人工標注，欄 = 模型輸出
    cm = Counter((r["human_label"].strip(), r["model_label"]) for r in labeled)

    lines = [
        "# 線上新聞標題人工抽測報告",
        "",
        f"抽測日：{date.today().isoformat()}；樣本 {len(labeled)} 則線上英文財經新聞標題"
        f"（來源 yfinance），人工標注與模型輸出比對。",
        "",
        f"## 一致率：{agreement:.1%}（{n_agree}/{len(labeled)}）",
        "",
        "## 混淆矩陣（列 = 人工標注、欄 = 模型輸出）",
        "",
        "| 人工＼模型 | " + " | ".join(LABEL_NAMES) + " |",
        "|---|" + "|".join("---" for _ in LABEL_NAMES) + "|",
    ]
    for human in LABEL_NAMES:
        cells = [str(cm.get((human, model), 0)) for model in LABEL_NAMES]
        lines.append(f"| {human} | " + " | ".join(cells) + " |")

    lines += [
        "",
        "## 分佈落差與限制討論",
        "",
        "- 訓練資料 Financial PhraseBank 是**分析師標注的財報／公告短句**，語體正式、"
        "多為對公司財務影響的直接陳述；線上新聞標題則常見疑問句、聳動措辭、"
        "與多家公司並列的複合敘述，兩者存在系統性分佈落差。",
        "- 抽測一致率通常低於測試集 Macro F1，這不是模型退化，而是**領域外（out-of-domain）"
        "泛化**的真實成本；誠實呈現此數字並分析錯誤型態，比只報測試集分數更有說服力。",
        "- 人工標注本身也有主觀性（同一標題不同人可能標 neutral/positive），"
        "一致率的分母包含這類邊界案例。",
        "",
        "> 由 `python tools/spot_check.py report` 產生，樣本與標注見 `docs/spot_check_sample.csv`。",
    ]
    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"一致率 {agreement:.1%}（{n_agree}/{len(labeled)}），報告已寫入 {REPORT_MD}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="線上標題人工抽測")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sample = sub.add_parser("sample", help="抓取線上標題並輸出待標注 CSV")
    p_sample.add_argument("--tickers", nargs="+", default=["AAPL", "TSLA", "NVDA", "MSFT", "GOOG"])
    p_sample.add_argument("--per-ticker", type=int, default=6)

    sub.add_parser("report", help="依已標注 CSV 計算一致率並產出報告")

    args = parser.parse_args()
    if args.command == "sample":
        return cmd_sample(args.tickers, args.per_ticker)
    return cmd_report()


if __name__ == "__main__":
    sys.exit(main())
