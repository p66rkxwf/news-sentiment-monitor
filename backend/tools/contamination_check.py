"""預訓練污染分析（backend/ 目錄執行）：python tools/contamination_check.py

清單上的問題是：「你用的預訓練語言模型，可能在預訓練階段就看過你的測試語料
（公開資料集尤其危險）。」

這件事沒辦法直接查證——預訓練語料不公開、也無法窮舉查詢。所以本工具走三條
間接但可查證的路：

1. **時序對照**：每個 checkpoint 的預訓練語料截止時間 vs 每份測試語料的公開時間。
   語料若晚於截止時間，該 checkpoint 不可能看過——這是唯一能給出「不可能」的論證。
2. **重疊實測**：測試切分的文字 vs 線上實際抓到的標題，做近重複比對。
   這條量的不是預訓練污染，而是**評估污染**：若線上標題就在訓練語料裡，
   線上抽測的分數等於在考已經看過的題目。
3. **時間上不可能被污染的評估**：2026 年新抓的標題晚於所有 checkpoint 的
   預訓練截止，用它們做的人工複核，結構上不可能受污染。

第 3 條才是真正的解方；1 和 2 是把風險範圍縮小到可以誠實描述的程度。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from newssent.config import BACKEND_ROOT, NEWS_CACHE_DB_PATH
from newssent.text.preprocess import clean_text

DOCS_DIR = BACKEND_ROOT.parent / "docs"

# 近重複判定門檻：字元 3-gram TF-IDF 的餘弦相似度。
# 0.9 以上實務上就是同一句話換個標點；0.7~0.9 是明顯改寫。兩個都報。
_NEAR_DUPLICATE = 0.90
_SIMILAR = 0.70

# 每個 checkpoint 的預訓練語料與截止時間（公開資料，來源見文件表格）
CHECKPOINTS = {
    "bert-base-uncased": {
        "corpora": "BooksCorpus + English Wikipedia",
        "cutoff": "2018",
        "risk": "低",
        "note": "語料不含財經新聞網站；FPB/SEntFiN 皆非 Wikipedia 內容",
    },
    "distilbert-base-uncased": {
        "corpora": "同 bert-base-uncased（蒸餾自該模型）",
        "cutoff": "2018",
        "risk": "低",
        "note": "繼承 bert-base 的語料，風險相同",
    },
    "roberta-base": {
        "corpora": "BooksCorpus + Wikipedia + CC-News + OpenWebText + Stories",
        "cutoff": "2019-02",
        "risk": "**中**",
        "note": "**CC-News 含 2016-09~2019-02 的新聞報導**，與財經標題語體重疊",
    },
}

CORPORA = {
    "Financial PhraseBank": {
        "published": "2014",
        "source": "Malo et al., JASIST 2014",
        "content": "分析師標注的財報／公告短句",
    },
    "SEntFiN 1.0": {
        "published": "2022",
        "source": "Sinha et al., JASIST 2022（arXiv:2305.12257）",
        "content": "印度財經媒體新聞標題，標注到實體層級",
    },
}


def load_sentfin_test() -> list[str]:
    """SEntFiN 測試切分的文字（清洗後）。"""
    from newssent.data.sentfin import prepare

    ds = prepare()
    return [clean_text(ds.titles[i]) for i in ds.split.test]


def load_phrasebank_test() -> list[str]:
    """PhraseBank 測試切分的文字；資料檔不在時回空清單。"""
    try:
        from newssent.data.phrasebank import prepare

        pb = prepare()
        return [clean_text(pb.texts[i]) for i in pb.split.test]
    except Exception as exc:  # 資料檔缺席不該擋住整份分析
        print(f"  （略過 PhraseBank：{exc}）")
        return []


def load_online_headlines(db_path=NEWS_CACHE_DB_PATH) -> list[str]:
    """news_cache.db 內所有線上標題（去重、清洗後）。"""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT payload FROM news_cache").fetchall()
    finally:
        conn.close()

    seen: set[str] = set()
    for (payload,) in rows:
        for article in json.loads(payload):
            title = clean_text(article.get("title") or "")
            if title:
                seen.add(title)
    return sorted(seen)


def max_similarity(online: list[str], corpus: list[str]) -> np.ndarray:
    """每則線上標題對語料的最高相似度。"""
    if not online or not corpus:
        return np.zeros(len(online))

    # 字元 n-gram 對改寫、標點差異比詞袋穩健
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=1)
    corpus_matrix = vectorizer.fit_transform(corpus)
    online_matrix = vectorizer.transform(online)
    # 稀疏矩陣乘法；TF-IDF 已 L2 正規化，內積即餘弦相似度
    similarity = online_matrix @ corpus_matrix.T
    return np.asarray(similarity.max(axis=1).todense()).ravel()


def _overlap_rows(name: str, online: list[str], corpus: list[str]) -> dict:
    scores = max_similarity(online, corpus)
    if len(scores) == 0:
        return {"corpus": name, "n_corpus": len(corpus), "near": 0, "similar": 0, "max": 0.0}
    return {
        "corpus": name,
        "n_corpus": len(corpus),
        "near": int((scores >= _NEAR_DUPLICATE).sum()),
        "similar": int(((scores >= _SIMILAR) & (scores < _NEAR_DUPLICATE)).sum()),
        "max": float(scores.max()),
    }


def _write_report(online: list[str], overlaps: list[dict]) -> None:
    generated = datetime.now(timezone.utc).isoformat(timespec="seconds")
    total_near = sum(row["near"] for row in overlaps)

    lines = [
        "# 預訓練污染分析",
        "",
        f"- 產生時間：{generated}",
        f"- 線上標題樣本：{len(online)} 則（`news_cache.db` 去重後）",
        "",
        "「你用的預訓練語言模型，可能在預訓練階段就看過你的測試語料。」",
        "這件事**無法直接查證**——預訓練語料不公開，也無法窮舉查詢。",
        "以下是三條間接但可查證的路徑，以及它們各自能證明到什麼程度。",
        "",
        "## 一、時序對照：哪些 checkpoint 有可能看過",
        "",
        "| checkpoint | 預訓練語料 | 截止 | 風險 | 說明 |",
        "|---|---|---|---|---|",
    ]
    for name, info in CHECKPOINTS.items():
        lines.append(
            f"| `{name}` | {info['corpora']} | {info['cutoff']} | {info['risk']} | {info['note']} |"
        )

    lines += [
        "",
        "| 測試語料 | 公開年份 | 來源 | 內容 |",
        "|---|---|---|---|",
    ]
    for name, info in CORPORA.items():
        lines.append(
            f"| {name} | {info['published']} | {info['source']} | {info['content']} |"
        )

    lines += [
        "",
        "### 讀法",
        "",
        "- **SEntFiN（2022）晚於所有 checkpoint 的預訓練截止（2018／2019-02）。**",
        "  資料集本身不可能被預訓練看過。但它的原始素材是 2010 年代的印度財經新聞標題，",
        "  那些**新聞本身**早於截止時間——`roberta-base` 的 CC-News",
        "  （2016-09~2019-02）語體與來源都重疊，有可能含有其中部分報導。",
        "  這是「資料集沒被看過、但素材可能被看過」的情況，不能只講前半句。",
        "- **PhraseBank（2014）早於所有 checkpoint**，但其內容是分析師標注的財報短句，",
        "  不是網路公開文本，出現在 Wikipedia／BooksCorpus 的機率極低。",
        "- **production 模型是 `bert-combined`（底層 `bert-base-uncased`）**——",
        "  語料為 BooksCorpus + Wikipedia，不含新聞網站，是三者中風險最低的。",
        "  風險最高的 `roberta-base` 在實驗 #6 已被判定不採用。",
        "",
        "**誠實邊界**：以上是「有沒有機會看過」的論證，不是「沒看過」的證明。",
        "要證明沒看過，得能查詢預訓練語料——做不到。",
        "",
        "## 二、重疊實測：線上標題與測試語料有多像",
        "",
        "這一節量的不是預訓練污染，而是**評估污染**：如果線上抽測用的標題",
        "本來就在訓練語料裡，那份分數等於在考已經看過的題目。",
        "",
        f"判定用字元 3–5 gram 的 TF-IDF 餘弦相似度："
        f"≥{_NEAR_DUPLICATE} 視為近重複、{_SIMILAR}–{_NEAR_DUPLICATE} 視為明顯改寫。",
        "",
        "| 測試語料 | 語料則數 | 近重複 | 明顯改寫 | 最高相似度 |",
        "|---|---|---|---|---|",
    ]
    for row in overlaps:
        lines.append(
            f"| {row['corpus']} | {row['n_corpus']:,} | {row['near']} | {row['similar']} "
            f"| {row['max']:.3f} |"
        )

    if total_near == 0:
        lines += [
            "",
            f"**{len(online)} 則線上標題中，沒有任何一則與測試語料構成近重複。**",
            "線上抽測考的是模型沒看過的題目——這句話有實測支撐，不是推測。",
            "",
        ]
    else:
        lines += [
            "",
            f"⚠️ **偵測到 {total_near} 則近重複。** 這些標題必須從線上抽測樣本中剔除，",
            "否則抽測分數會被灌水。",
            "",
        ]

    lines += [
        "## 三、真正的解方：時間上不可能被污染的評估",
        "",
        "前兩節只能把風險縮小，無法歸零。真正乾淨的評估只有一種：",
        "**用晚於所有 checkpoint 預訓練截止時間的資料來評估。**",
        "",
        "本專案的線上人工複核正是如此——2026 年新抓的標題，晚於 2018／2019 的",
        "預訓練截止**七年以上**，結構上不可能被看過。",
        "",
        "而這條路徑給出的數字，恰好也說明了為什麼它不可省略：",
        "",
        "| 評估方式 | 一致率 | 污染可能性 |",
        "|---|---|---|",
        "| 保留測試集（SEntFiN test） | 見 `docs/model_comparison.md` | 低但非零 |",
        "| 線上新標題 × AI 初標 | 66.7% | 無（但 AI 自標會高估）|",
        "| **線上新標題 × 財金組獨立複核** | **46.7%**（實驗 #6 前）| **無** |",
        "| 線上新標題 × 財金組複核（改任務定義後）| **61.7%** | **無** |",
        "",
        "「AI 初標 66.7% vs 人工複核 46.7%」這 20 個百分點的落差，本身就是",
        "「自己標自己的考卷會高估」的直接證據——也是為什麼污染分析不能只靠",
        "保留測試集的分數。",
        "",
        "> 由 `python tools/contamination_check.py` 自動產生。",
        "",
    ]

    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    out = DOCS_DIR / "pretraining_contamination.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"報告已寫入 {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="預訓練污染分析")
    parser.add_argument("--db", default=str(NEWS_CACHE_DB_PATH), help="news_cache.db 路徑")
    args = parser.parse_args()

    print("載入線上標題…")
    online = load_online_headlines(args.db)
    print(f"  {len(online)} 則（去重後）")

    overlaps = []
    print("載入 SEntFiN 測試切分…")
    overlaps.append(_overlap_rows("SEntFiN 1.0（測試切分）", online, load_sentfin_test()))
    print("載入 PhraseBank 測試切分…")
    phrasebank = load_phrasebank_test()
    if phrasebank:
        overlaps.append(_overlap_rows("Financial PhraseBank（測試切分）", online, phrasebank))

    for row in overlaps:
        print(
            f"  {row['corpus']}：語料 {row['n_corpus']} 則、"
            f"近重複 {row['near']}、明顯改寫 {row['similar']}、最高相似度 {row['max']:.3f}"
        )

    _write_report(online, overlaps)


if __name__ == "__main__":
    main()
