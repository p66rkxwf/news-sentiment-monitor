"""關鍵字雲：對近期標題做 TF-IDF 計分，取全庫加總最高的詞。

停用詞與 ticker 本身必須剔除——否則每檔股票的關鍵字雲都被自己的名字佔滿
（PLAN.md Phase 5）。純函式，輸入為 clean_text() 後的標題清單。
"""

from __future__ import annotations


def extract_keywords(titles: list[str], ticker: str, top_n: int = 15) -> list[tuple[str, float]]:
    from sklearn.feature_extraction.text import TfidfVectorizer

    if not titles:
        return []

    # max_df=0.8：出現在 8 成以上標題的詞（幾乎必是公司名本身）自動剔除，
    # 否則每檔股票的關鍵字雲都被自己的名字佔滿；標題太少全被 max_df 濾掉時退一步重試
    try:
        vectorizer = TfidfVectorizer(
            stop_words="english", ngram_range=(1, 1), max_features=500, max_df=0.8
        )
        matrix = vectorizer.fit_transform(titles)
    except ValueError:
        try:
            vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 1), max_features=500)
            matrix = vectorizer.fit_transform(titles)
        except ValueError:  # 全部標題都只含停用詞
            return []

    scores = matrix.sum(axis=0).A1
    words = vectorizer.get_feature_names_out()

    banned = {ticker.lower(), ticker.lower().replace(".", "")}
    ranked = sorted(
        (
            (w, float(s))
            for w, s in zip(words, scores)
            if w.lower() not in banned and not w.isdigit()
        ),
        key=lambda t: t[1],
        reverse=True,
    )
    return [(w, round(s, 4)) for w, s in ranked[:top_n]]
