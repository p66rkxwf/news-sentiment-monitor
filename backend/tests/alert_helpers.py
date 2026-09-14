"""情緒預警測試共用：造一段合成的交易日序列與逐則分數，不打網路、不需要模型。"""

from datetime import date, timedelta

from newssent.config import LABEL_NAMES
from newssent.data.finmind_news import FINMIND_PROVIDER
from newssent.data.provider import Article
from newssent.data.score_store import ScoreStore, utc_days
from newssent.inference.alerts import session_open

ONE_HOT = {name: tuple(1.0 if n == name else 0.0 for n in LABEL_NAMES) for name in LABEL_NAMES}

# 平靜日交錯兩種：分數 1/3 與 0（平均 1/6、樣本標準差 ≈ 0.171）
CALM_DAYS = [["positive", "neutral", "neutral"], ["positive", "negative", "neutral"]]


def weekdays(start: date, count: int) -> list[date]:
    out, day = [], start
    while len(out) < count:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def fill(
    store: ScoreStore,
    ticker: str,
    sessions: list[date],
    last_day_labels: list[str],
    scorer: str,
    unfetched: set[date] = frozenset(),
) -> None:
    """sessions[0] 為左邊界；中間填平靜日，最後一個交易日填 last_day_labels。

    每則標題發在該交易日開盤前 2 小時，並把整段 UTC 日標記為已抓（unfetched 除外）。
    """
    for i, session in enumerate(sessions[1:], start=1):
        labels = last_day_labels if i == len(sessions) - 1 else CALM_DAYS[i % 2]
        base = session_open(session) - timedelta(hours=2)
        articles = [
            Article(
                title=f"{ticker} {session} #{k}",
                url="",
                published_at=(base + timedelta(minutes=k)).isoformat(),
                source="測試社",
            )
            for k in range(len(labels))
        ]
        store.upsert_headlines(ticker, articles, origin="backfill")
        store.save_scores(ticker, scorer, [(a.title, *ONE_HOT[label]) for a, label in zip(articles, labels)])
    for day in utc_days(sessions[0], sessions[-1]):
        if day not in unfetched:
            store.mark_fetched(ticker, day, FINMIND_PROVIDER, 3)
    store.save_sessions(sessions)
