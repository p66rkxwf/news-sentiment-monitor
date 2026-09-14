"""情緒預警的標題與分數庫（SQLite）。

四張表、各管一件事：
- headlines：抓到的原始標題（依 ticker＋標題去重，保留最早的發布時間）
- headline_scores：每個評分器版本對每則標題的三類機率
- fetch_log：哪些 (ticker, UTC 日) 已完整抓過——回補可中斷續跑、不重複打 API
- trading_sessions：已確認的台股交易日

為什麼存逐則而不是每日分數：換評分器、改聚合規則、修正交易日歸屬時只要重算、不必重抓；
警示也要能列出「是哪幾則標題」觸發的（可稽核）。抓取與評分分兩步存，
LLM 中途掛掉時已抓的標題不會遺失，下次只補評分。

origin：live＝該 UTC 日結束後 48 小時內抓到；backfill＝事後回補。回補資料的發布時間是
資料源宣稱的，不代表系統當時真的抓得到（新聞可能事後被刪或補登）——回測報告須分開陳述。
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from newssent.data.provider import Article

_SCHEMA = """
CREATE TABLE IF NOT EXISTS headlines (
    ticker TEXT NOT NULL,
    title TEXT NOT NULL,
    published_at TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL DEFAULT '',
    fetched_at TEXT,
    origin TEXT NOT NULL CHECK (origin IN ('live', 'backfill')),
    PRIMARY KEY (ticker, title)
);
CREATE INDEX IF NOT EXISTS idx_headlines_time ON headlines (ticker, published_at);
CREATE TABLE IF NOT EXISTS headline_scores (
    ticker TEXT NOT NULL,
    title TEXT NOT NULL,
    scorer TEXT NOT NULL,
    p_negative REAL NOT NULL,
    p_neutral REAL NOT NULL,
    p_positive REAL NOT NULL,
    scored_at TEXT NOT NULL,
    PRIMARY KEY (ticker, title, scorer)
);
CREATE TABLE IF NOT EXISTS fetch_log (
    ticker TEXT NOT NULL,
    utc_day TEXT NOT NULL,
    provider TEXT NOT NULL,
    n_articles INTEGER NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (ticker, utc_day, provider)
);
CREATE TABLE IF NOT EXISTS trading_sessions (
    session TEXT PRIMARY KEY
);
"""


@dataclass(frozen=True)
class ScoredHeadline:
    title: str
    source: str
    url: str
    published_at: datetime  # UTC
    origin: str
    p_negative: float
    p_neutral: float
    p_positive: float


def utc_days(start: date, end: date) -> Iterator[date]:
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)


def _to_utc_iso(value: str | datetime) -> str:
    """統一存成 UTC、秒精度的 ISO 字串——字串比較才等於時間先後比較。"""
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError(f"時間缺時區，無法判斷資訊時點：{value!r}")
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ScoreStore:
    def __init__(self, db_path: Path | str):
        # 與 NewsCache 相同：FastAPI 同步路由在 worker 執行緒，需 check_same_thread=False 並以 lock 序列化
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # --- 標題 ---
    def upsert_headlines(self, ticker: str, articles: Iterable[Article], origin: str) -> None:
        rows = [
            (ticker, a.title, _to_utc_iso(a.published_at), a.url, a.source, a.fetched_at, origin)
            for a in articles
            if a.title and a.published_at
        ]
        # UPDATE 右側一律讀舊值，所以 CASE 比較的是「既有的」發布時間
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO headlines (ticker, title, published_at, url, source, fetched_at, origin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (ticker, title) DO UPDATE SET
                    url = CASE WHEN excluded.published_at < headlines.published_at
                               THEN excluded.url ELSE headlines.url END,
                    source = CASE WHEN excluded.published_at < headlines.published_at
                                  THEN excluded.source ELSE headlines.source END,
                    published_at = MIN(headlines.published_at, excluded.published_at)
                """,
                rows,
            )
            self._conn.commit()

    # --- 抓取紀錄 ---
    def mark_fetched(self, ticker: str, utc_day: date, provider: str, n_articles: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO fetch_log VALUES (?, ?, ?, ?, ?)",
                (ticker, utc_day.isoformat(), provider, n_articles, _now_iso()),
            )
            self._conn.commit()

    def fetched_days(self, ticker: str, provider: str) -> set[date]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT utc_day FROM fetch_log WHERE ticker = ? AND provider = ?", (ticker, provider)
            ).fetchall()
        return {date.fromisoformat(r[0]) for r in rows}

    # --- 評分 ---
    def unscored(self, ticker: str, scorer: str) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT h.title FROM headlines h
                LEFT JOIN headline_scores s
                  ON s.ticker = h.ticker AND s.title = h.title AND s.scorer = ?
                WHERE h.ticker = ? AND s.title IS NULL
                ORDER BY h.published_at
                """,
                (scorer, ticker),
            ).fetchall()
        return [r[0] for r in rows]

    def save_scores(
        self, ticker: str, scorer: str, scores: Iterable[tuple[str, float, float, float]]
    ) -> None:
        now = _now_iso()
        with self._lock:
            self._conn.executemany(
                "INSERT OR REPLACE INTO headline_scores VALUES (?, ?, ?, ?, ?, ?, ?)",
                [(ticker, title, scorer, neg, neu, pos, now) for title, neg, neu, pos in scores],
            )
            self._conn.commit()

    def scored_headlines(
        self, ticker: str, scorer: str, start: datetime, end: datetime
    ) -> list[ScoredHeadline]:
        """發布時間落在 [start, end) 且已由該評分器評分的標題，依時間排序。"""
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT h.title, h.source, h.url, h.published_at, h.origin,
                       s.p_negative, s.p_neutral, s.p_positive
                FROM headlines h
                JOIN headline_scores s ON s.ticker = h.ticker AND s.title = h.title
                WHERE h.ticker = ? AND s.scorer = ? AND h.published_at >= ? AND h.published_at < ?
                ORDER BY h.published_at
                """,
                (ticker, scorer, _to_utc_iso(start), _to_utc_iso(end)),
            ).fetchall()
        return [
            ScoredHeadline(
                title=r[0], source=r[1], url=r[2], published_at=datetime.fromisoformat(r[3]),
                origin=r[4], p_negative=r[5], p_neutral=r[6], p_positive=r[7],
            )
            for r in rows
        ]

    # --- 交易日曆 ---
    def save_sessions(self, sessions: Iterable[date]) -> None:
        with self._lock:
            self._conn.executemany(
                "INSERT OR IGNORE INTO trading_sessions VALUES (?)", [(s.isoformat(),) for s in sessions]
            )
            self._conn.commit()

    def sessions(self) -> list[date]:
        with self._lock:
            rows = self._conn.execute("SELECT session FROM trading_sessions ORDER BY session").fetchall()
        return [date.fromisoformat(r[0]) for r in rows]
