"""時間戳語意實測（backend/ 目錄執行）：python tools/timestamp_lag.py

清單上的問題是：「每個欄位的時間戳是『事件發生時間』『資料發布時間』還是
『你抓到的時間』？三者差幾小時？新聞資料上這個差異最致命。」

這支工具用**既有的 news_cache.db** 回答其中可回答的部分——不需要重抓資料，
因為快取的每一列本來就同時存著 `created_at`（我們寫入快取的時刻）與 payload 裡
每則新聞的 `published_at`（資料源宣稱的發布時刻）。兩者相減就是實測落差。

三個時間戳裡，**「事件發生時間」資料源根本不提供**，這點必須誠實承認而不是
拿發布時間假裝。詳見產出的 docs/timestamp_semantics.md。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone

import numpy as np

from newssent.config import BACKEND_ROOT, NEWS_CACHE_DB_PATH

DOCS_DIR = BACKEND_ROOT.parent / "docs"


def _parse_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def collect_lags(db_path=NEWS_CACHE_DB_PATH) -> tuple[list[float], int, int]:
    """回傳 (逐則落差小時數, 總則數, 無法解析則數)。"""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT payload, created_at FROM news_cache").fetchall()
    finally:
        conn.close()

    lags: list[float] = []
    total = 0
    unparsed = 0
    for payload, created_at in rows:
        fetched = datetime.fromtimestamp(float(created_at), tz=timezone.utc)
        for article in json.loads(payload):
            total += 1
            # fetched_at 是 2026-08 才加的欄位；舊快取沒有，退回用該列的 created_at
            stamped = _parse_iso(article.get("fetched_at") or "")
            published = _parse_iso(article.get("published_at") or "")
            if published is None:
                unparsed += 1
                continue
            lags.append(((stamped or fetched) - published).total_seconds() / 3600.0)
    return lags, total, unparsed


def _percentiles(lags: list[float]) -> dict[str, float]:
    array = np.asarray(lags)
    return {
        "min": float(array.min()),
        "p25": float(np.percentile(array, 25)),
        "median": float(np.median(array)),
        "p75": float(np.percentile(array, 75)),
        "p95": float(np.percentile(array, 95)),
        "max": float(array.max()),
        "mean": float(array.mean()),
    }


def _write_report(lags: list[float], total: int, unparsed: int) -> None:
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# 新聞資料的時間戳語意",
        "",
        f"- 產生時間：{generated}",
        f"- 樣本：`news_cache.db` 內 {total} 則新聞（{len(lags)} 則可解析發布時間、"
        f"{unparsed} 則無法解析）",
        "",
        "## 三個時間戳，只有兩個拿得到",
        "",
        "| 時間戳 | 語意 | 本專案是否有 | 來源 |",
        "|---|---|---|---|",
        "| 事件發生時間 | 事情**實際發生**的時刻 | ❌ **沒有** | 資料源不提供 |",
        "| 資料發布時間 | 媒體**發稿**的時刻 | ✅ `Article.published_at` | "
        "NewsAPI `publishedAt`／yfinance `pubDate` |",
        "| 抓取時間 | 本系統**取得**的時刻 | ✅ `Article.fetched_at` | "
        "`CachedNewsProvider.get_news()` 蓋章 |",
        "",
        "**事件發生時間拿不到，這點必須明講而不是拿發布時間頂替。**",
        "一則「Q2 財報優於預期」的稿子，發布時間是盤後某個時刻，但「Q2」這個事件",
        "橫跨三個月。兩者的落差無法從資料裡補回來——只能承認模型看到的是",
        "「新聞被寫出來的時間」，不是「事情發生的時間」。",
        "",
        "## 發布 → 抓取 的實測落差",
        "",
    ]

    if not lags:
        lines += [
            "快取內沒有可解析的發布時間，無法計算落差。",
            "先讓 API 或 `tools/spot_check.py` 跑過一輪累積快取，再重跑本工具。",
            "",
        ]
    else:
        stats = _percentiles(lags)
        lines += [
            "| 統計量 | 落差（小時） |",
            "|---|---|",
            f"| 最小 | {stats['min']:.2f} |",
            f"| 25 百分位 | {stats['p25']:.2f} |",
            f"| **中位數** | **{stats['median']:.2f}** |",
            f"| 75 百分位 | {stats['p75']:.2f} |",
            f"| 95 百分位 | {stats['p95']:.2f} |",
            f"| 最大 | {stats['max']:.2f} |",
            f"| 平均 | {stats['mean']:.2f} |",
            "",
            f"中位數 **{stats['median']:.1f} 小時**——這是新聞發稿到本系統看見它之間的",
            "實際延遲。負值代表資料源的發布時間戳晚於我們的抓取時間（時區或時鐘偏移），",
            "若大量出現就是時間戳本身不可信的訊號。",
            "",
        ]
        negative = sum(1 for lag in lags if lag < 0)
        if negative:
            lines += [
                f"⚠️ 有 {negative} 則（{negative / len(lags):.1%}）落差為負，"
                "代表這些則的發布時間戳晚於抓取時間，該來源的時間戳不可盡信。",
                "",
            ]

    lines += [
        "## 對本專案的影響",
        "",
        "**目前沒有影響，因為線上情緒指數不做時間對齊。** `/api/sentiment` 拿的是",
        "「此刻抓得到的最近 N 則新聞」，直接判讀後彙總，不與任何價格序列做時點比對。",
        "沒有 as-of join，就沒有對錯位的機會。",
        "",
        "**但只要哪天要做「新聞情緒 → 隔日報酬」的回測，這個落差立刻致命**：",
        "屆時必須以 `fetched_at`（不是 `published_at`）為可用時點，",
        "否則就是假設自己在新聞發稿的當下就讀到了它——那是前視偏誤。",
        "`fetched_at` 欄位現在就開始記錄，正是為了讓那一天有東西可用。",
        "",
        "> 由 `python tools/timestamp_lag.py` 自動產生。",
        "",
    ]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "timestamp_semantics.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="新聞時間戳落差實測")
    parser.add_argument("--db", default=str(NEWS_CACHE_DB_PATH), help="news_cache.db 路徑")
    args = parser.parse_args()

    lags, total, unparsed = collect_lags(args.db)
    if lags:
        stats = _percentiles(lags)
        print(
            f"{total} 則新聞，發布→抓取落差中位數 {stats['median']:.2f} 小時"
            f"（p95 {stats['p95']:.2f}、最大 {stats['max']:.2f}）"
        )
    else:
        print(f"{total} 則新聞，無可解析的發布時間")
    _write_report(lags, total, unparsed)


if __name__ == "__main__":
    main()
