"""情緒異常預警：逐則標題情緒 → 每個交易日的情緒分數 → 與該股自己近 20 個交易日的常態比較。

一、情緒分數
  每則標題 score = P(positive) − P(negative)，範圍 [−1, +1]；
  交易日分數 = 該交易日所有標題 score 的平均。評分器只給標籤（如 LLM）時機率為 one-hot，
  平均即「(正面則數 − 負面則數) / 總則數」。

二、資訊時點（回測最容易不小心作弊的地方）
  標題歸到「發布之後第一個開盤的交易日」：交易日 s 的標題窗是 [前一交易日開盤, s 開盤)。
  所以對 s 的判斷在 s 開盤**前**就能給出，不含 s 盤中才出現的消息；
  休市期間（週末、春節、清明連假）累積的標題全部歸到休市後第一個交易日。
  回測說「事件前 N 個交易日偵測到」的 N 一律依此定義計算。

三、判斷規則
  z = (當日分數 − 基準期平均) / max(基準期標準差, σ 下限)
  基準期 = 當日**之前**的 20 個交易日（不含當日，否則當日的惡化會拉低自己的基準而稀釋 z）。
  z < −2 → high；z < −1.5 → watch；其餘 normal。
  資料不足回傳 insufficient——「沒資料」與「正常」是兩回事，不得當成綠燈。

四、盤勢報導不計入
  「台積電跌40元」這類標題只是在描述已經發生的價格變化，會被判負面卻不含新資訊；
  不排除的話，示警會變成「昨天已經跌了」的回聲。規則與代價見 config.ALERT_PRICE_REPORT_PATTERNS。

純函式、不碰網路與資料庫，參數讀 config。
"""

from __future__ import annotations

import bisect
import re
import statistics
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import StrEnum

from newssent.config import (
    ALERT_BASELINE_SESSIONS,
    ALERT_HIGH_Z,
    ALERT_MARKET_OPEN_HOUR,
    ALERT_MARKET_UTC_OFFSET_HOURS,
    ALERT_MIN_ARTICLES,
    ALERT_MIN_BASELINE_DAYS,
    ALERT_PRICE_REPORT_PATTERNS,
    ALERT_SIGMA_FLOOR,
    ALERT_WATCH_Z,
    ALERT_WINDOW_SESSIONS,
)

# 固定位移而非 zoneinfo：Windows 沒有內建時區資料庫，而台灣沒有日光節約時間
MARKET_TZ = timezone(timedelta(hours=ALERT_MARKET_UTC_OFFSET_HOURS))

_PRICE_REPORT_RE = re.compile("|".join(f"(?:{p})" for p in ALERT_PRICE_REPORT_PATTERNS))


def is_price_report(title: str) -> bool:
    """標題是否為盤勢報導；先做 NFKC 正規化，全形數字（「跌４０元」）才比對得到。"""
    return bool(_PRICE_REPORT_RE.search(unicodedata.normalize("NFKC", title or "")))


class AlertLevel(StrEnum):
    HIGH = "high"
    WATCH = "watch"
    NORMAL = "normal"
    INSUFFICIENT = "insufficient"


@dataclass(frozen=True)
class AlertParams:
    window_sessions: int = ALERT_WINDOW_SESSIONS
    baseline_sessions: int = ALERT_BASELINE_SESSIONS
    watch_z: float = ALERT_WATCH_Z
    high_z: float = ALERT_HIGH_Z
    min_articles: int = ALERT_MIN_ARTICLES
    min_baseline_days: int = ALERT_MIN_BASELINE_DAYS
    sigma_floor: float = ALERT_SIGMA_FLOOR


@dataclass(frozen=True)
class DailyScore:
    session: date
    score: float | None  # None = 該交易日沒有任何標題
    n: int


@dataclass(frozen=True)
class Assessment:
    session: date
    level: AlertLevel
    reason: str | None           # insufficient 時說明缺什麼
    score: float | None
    n: int
    z: float | None
    baseline_mean: float | None
    baseline_std: float | None   # 實際標準差（未套下限），供展示
    baseline_days: int
    recent: list[DailyScore]
    recent_score: float | None   # 近 window 個交易日、依則數加權的分數

    @property
    def change(self) -> float | None:
        """當日分數相對基準期平均的變化量。"""
        if self.score is None or self.baseline_mean is None:
            return None
        return self.score - self.baseline_mean


def headline_score(p_negative: float, p_positive: float) -> float:
    return p_positive - p_negative


def session_open(session: date) -> datetime:
    return datetime.combine(session, time(ALERT_MARKET_OPEN_HOUR), tzinfo=MARKET_TZ)


def _bucket_index(opens: list[datetime], published_at: datetime) -> int:
    if published_at.tzinfo is None:
        # naive 時間無從判斷時區；轉成帶時區是資料源的責任（例：FinMind 的 naive 時間是 UTC）
        raise ValueError(f"published_at 必須帶時區：{published_at!r}")
    return bisect.bisect_right(opens, published_at)


def session_for(published_at: datetime, sessions: Sequence[date]) -> date | None:
    """標題可被使用的第一個交易日（開盤時間嚴格晚於發布時間）；超出行事曆回傳 None。"""
    ordered = sorted(sessions)
    i = _bucket_index([session_open(s) for s in ordered], published_at)
    return ordered[i] if i < len(ordered) else None


def extend_sessions(sessions: Sequence[date], now: datetime) -> list[date]:
    """在已確認的交易日之後逐一補上平日，直到出現「開盤時間晚於 now」的交易日為止。

    已確認交易日來自加權指數實際成交日；尚未發生的交易日只能推估（不知道國定假日）。
    推錯的日子會在下次更新日曆時消失，而分數每次都從逐則標題重算，標題會自動歸回正確交易日。
    """
    out = sorted(sessions)
    if not out:
        return out
    candidate = out[-1]
    while session_open(out[-1]) <= now:
        candidate += timedelta(days=1)
        if candidate.weekday() < 5:
            out.append(candidate)
    return out


def daily_scores(
    scored: Iterable[tuple[datetime, float]], sessions: Sequence[date]
) -> list[DailyScore]:
    """把 (發布時間, 標題分數) 聚合成每個交易日的分數。

    sessions[0] 只當左邊界、不輸出：交易日 s 的標題窗是 [前一交易日開盤, s 開盤)，
    第一個交易日沒有「前一日」可界定窗口，硬算會把更早的所有標題都塞進去。
    晚於最後一個交易日開盤的標題屬於行事曆之外的未來交易日，同樣略過。
    """
    ordered = sorted(sessions)
    opens = [session_open(s) for s in ordered]
    sums = [0.0] * len(ordered)
    counts = [0] * len(ordered)
    for published_at, score in scored:
        i = _bucket_index(opens, published_at)
        if 1 <= i < len(ordered):
            sums[i] += score
            counts[i] += 1
    return [
        DailyScore(session=s, score=(sums[i] / counts[i]) if counts[i] else None, n=counts[i])
        for i, s in enumerate(ordered)
        if i >= 1
    ]


def assess(series: Sequence[DailyScore], params: AlertParams = AlertParams()) -> Assessment:
    """判斷 series 最後一個交易日的警示等級；series 須依交易日遞增排序。"""
    if not series:
        raise ValueError("series 不可為空")

    today = series[-1]
    baseline = [
        d.score for d in series[-(params.baseline_sessions + 1):-1] if d.score is not None
    ]
    recent = list(series[-params.window_sessions:])
    recent_n = sum(d.n for d in recent)
    recent_score = (
        sum(d.score * d.n for d in recent if d.score is not None) / recent_n if recent_n else None
    )
    mean = statistics.fmean(baseline) if baseline else None
    std = statistics.stdev(baseline) if len(baseline) >= 2 else None

    reason = None
    if today.n < params.min_articles:
        reason = f"當日標題 {today.n} 則，少於 {params.min_articles} 則"
    elif len(baseline) < max(params.min_baseline_days, 2):
        reason = f"基準期有新聞的交易日 {len(baseline)} 天，少於 {params.min_baseline_days} 天"

    if reason is not None:
        level, z = AlertLevel.INSUFFICIENT, None
    else:
        z = (today.score - mean) / max(std, params.sigma_floor)
        if z < params.high_z:
            level = AlertLevel.HIGH
        elif z < params.watch_z:
            level = AlertLevel.WATCH
        else:
            level = AlertLevel.NORMAL

    return Assessment(
        session=today.session,
        level=level,
        reason=reason,
        score=today.score,
        n=today.n,
        z=z,
        baseline_mean=mean,
        baseline_std=std,
        baseline_days=len(baseline),
        recent=recent,
        recent_score=recent_score,
    )
