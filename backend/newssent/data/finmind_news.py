"""FinMind TaiwanStockNews：台股個股中文新聞（2020-04 起、免費），情緒預警的歷史與每日新聞源。

以下資料源事實皆為 2026-09-14 實測。寫在這裡，是因為每一條都會讓回測默默出錯：
- `date` 欄位是 **UTC** 的 naive 字串。證據：2025-02-03「廣達一度觸跌停」標在 01:38，
  只有解讀成 UTC（台北 09:38，已開盤）才說得通。誤當台北時間，盤中消息會被提前 8 小時變成「盤前」。
- 單次請求只給一個 UTC 日（帶 end_date 回 400）。
- 匿名每小時 300 次、註冊 token 600 次，client 依此節流。
- 大量條目是 CMoney「股市爆料同學會」的**論壇貼文**，不是新聞，一律濾除。
- 同一則新聞會被 Yahoo 股市、Yahoo 新聞、豐雲學堂等轉載多次、時間各異：
  依標題去重、保留最早的發布時間（最早可得的時點才是資訊到達的時刻）。
- 標題尾巴帶「 - 來源名」，會讓轉載的同一則新聞看起來像不同標題，而且不是內容，去掉。
"""

from __future__ import annotations

import time
from datetime import date, datetime, timezone

from newssent.data.provider import Article

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"
FINMIND_PROVIDER = "finmind"
FORUM_MARKERS = ("股市爆料同學會",)


class FinMindError(RuntimeError):
    """FinMind 回傳非成功狀態（額度用盡、參數錯誤等）。"""


def parse_utc(raw: str) -> datetime:
    return datetime.strptime(raw.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def clean_title(title: str, source: str) -> str:
    title = (title or "").strip()
    suffix = f" - {source}" if source else ""
    if suffix and title.endswith(suffix):
        title = title[: -len(suffix)].rstrip()
    return title


def parse_rows(rows: list[dict], fetched_at: str | None = None) -> list[Article]:
    """FinMind 原始列 → Article（濾論壇、去來源尾綴、依標題去重取最早），依發布時間排序。"""
    earliest: dict[str, tuple[datetime, Article]] = {}
    for row in rows:
        raw_title = row.get("title") or ""
        if not raw_title or not row.get("date") or any(m in raw_title for m in FORUM_MARKERS):
            continue
        source = (row.get("source") or "").strip()
        title = clean_title(raw_title, source)
        if not title:
            continue
        published = parse_utc(row["date"])
        if title in earliest and earliest[title][0] <= published:
            continue
        earliest[title] = (
            published,
            Article(
                title=title,
                url=row.get("link") or "",
                published_at=published.isoformat(),
                source=source,
                fetched_at=fetched_at,
            ),
        )
    return [article for _, article in sorted(earliest.values(), key=lambda pair: pair[0])]


class FinMindNewsClient:
    def __init__(self, token: str = "", min_interval: float | None = None, timeout: float = 60.0):
        self._token = token
        # 300 次/時＝每 12 秒一次；600 次/時＝每 6 秒一次（各留一點餘裕）
        self._min_interval = min_interval if min_interval is not None else (6.5 if token else 12.5)
        self._timeout = timeout
        self._last_call = 0.0

    def fetch_day(self, stock_id: str, utc_day: date) -> list[Article]:
        import httpx

        wait = self._min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        headers = {"Authorization": f"Bearer {self._token}"} if self._token else {}
        try:
            resp = httpx.get(
                FINMIND_API_URL,
                params={"dataset": "TaiwanStockNews", "data_id": stock_id, "start_date": utc_day.isoformat()},
                headers=headers,
                timeout=self._timeout,
            )
        finally:
            self._last_call = time.monotonic()
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("status") != 200:
            raise FinMindError(f"FinMind {stock_id} {utc_day}: {payload.get('msg')}")
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return parse_rows(payload.get("data") or [], fetched_at=fetched_at)
