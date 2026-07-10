"""SQLite 新聞快取，以及 ticker 格式驗證。

ticker 會被用來組快取 key 與外部 API query，未驗證直接使用等於開放注入。
快取以「ticker + 時間桶」為 key：同一 ticker 在同一時間桶內只需打一次外部 API，
用來對付 NewsAPI 免費層每日 100 requests 的限制。
"""

import json
import re
import sqlite3
import threading
import time
from pathlib import Path

from newssent.config import TICKER_PATTERN

_TICKER_RE = re.compile(TICKER_PATTERN)


class InvalidTickerError(ValueError):
    """ticker 格式不符合美股代號規則。"""


def validate_ticker(ticker: str) -> str:
    if not _TICKER_RE.match(ticker):
        raise InvalidTickerError(f"不合法的股票代號格式: {ticker!r}")
    return ticker


def time_bucket(bucket_seconds: int, now: float | None = None) -> int:
    """回傳目前所屬時間桶編號；同桶內視為同一份快取。"""
    now = time.time() if now is None else now
    return int(now // bucket_seconds)


class NewsCache:
    """SQLite 快取：key = (ticker, bucket)，value = JSON 化的文章清單。"""

    def __init__(self, db_path: Path):
        self._db_path = db_path
        # FastAPI 的同步路由跑在 worker 執行緒，與建立連線的 lifespan 執行緒不同，
        # 故需 check_same_thread=False，並以 lock 序列化存取（demo 併發量低，足夠）
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS news_cache (
                ticker TEXT NOT NULL,
                bucket INTEGER NOT NULL,
                payload TEXT NOT NULL,
                created_at REAL NOT NULL,
                PRIMARY KEY (ticker, bucket)
            )
            """
        )
        self._conn.commit()

    def read(self, ticker: str, bucket: int) -> list[dict] | None:
        validate_ticker(ticker)
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM news_cache WHERE ticker = ? AND bucket = ?",
                (ticker, bucket),
            ).fetchone()
        return json.loads(row[0]) if row is not None else None

    def read_latest(self, ticker: str) -> list[dict] | None:
        """取最近一次快取（用於連網失敗時的降級退回，不論時間桶是否過期）。"""
        validate_ticker(ticker)
        with self._lock:
            row = self._conn.execute(
                "SELECT payload FROM news_cache WHERE ticker = ? ORDER BY bucket DESC LIMIT 1",
                (ticker,),
            ).fetchone()
        return json.loads(row[0]) if row is not None else None

    def write(self, ticker: str, bucket: int, articles: list[dict]) -> None:
        validate_ticker(ticker)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO news_cache (ticker, bucket, payload, created_at) VALUES (?, ?, ?, ?)",
                (ticker, bucket, json.dumps(articles), time.time()),
            )
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
