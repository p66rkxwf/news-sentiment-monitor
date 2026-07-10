# 基於自然語言處理之新聞情緒分析與即時監控系統

彰師大 115 年百萬專題探索（跨域整合類）。透過 NLP 技術自動擷取美股財經新聞並即時分析市場情緒，將非結構化文字轉化為可量化的情緒指標，輔助投資決策。

> 完整開發計畫見 [PLAN.md](PLAN.md)。**Phase 0（專案初始化 + API 契約凍結）骨架已完成**：單一 package、`clean_text()` 共用入口、`NewsProvider` 介面（含快取降級）、去重＋分層切分、情緒指數純函式、FastAPI mock endpoints 與 pytest（`FakeProvider`，不打網路）。Phase 1 起（PhraseBank 資料、五模型、真實推論、前端）尚未實作。

## 系統概觀

```
使用者輸入股票代號（如 AAPL）
        │
        ▼
 Next.js 前端儀表板 ──► FastAPI 後端 ──► NewsProvider（NewsAPI + 快取降級）
   · 情緒指針                │
   · 關鍵字雲                ▼
   · 新聞情緒列表      情緒分類模型（五模型比較後選出的最佳者）
```

## 技術棧

| 層 | 技術 |
|---|---|
| 訓練資料 | Financial PhraseBank（sentences_50agree，約 4,846 筆標注句） |
| 即時新聞 | NewsAPI（主）、yfinance news（備援） |
| 基線模型 | TF-IDF + Logistic Regression、TF-IDF + SVM |
| 深度模型 | DistilBERT / BERT / RoBERTa fine-tuning（PyTorch CUDA + Hugging Face） |
| 後端 | FastAPI（Python，單一 package `newssent/`） |
| 前端 | Next.js + TypeScript + Tailwind |
| 評估指標 | Accuracy、Macro F1、推論速度（GPU/CPU 分列） |

## 目錄導覽

```
backend/
  newssent/         # 單一 Python package（訓練與 API 服務共用）
    config.py       # 唯一設定來源（標籤順序、切分 seed、快取 TTL…）
    data/           # PhraseBank 處理、NewsProvider 介面、新聞快取
    text/           # clean_text()：訓練/推論唯一共用前處理入口
    ml/             # 五模型訓練、評估、比較、artifact registry
    inference/      # ticker→新聞→情緒→彙總指數→關鍵字
    api/            # FastAPI routers、schemas、錯誤契約
  artifacts/        # 模型權重與 metadata.json
  data/             # 資料集原始檔與切分索引
  tests/            # pytest（FakeProvider，不打網路）
frontend/
  app/              # Next.js 主頁
  components/       # SentimentGauge、KeywordCloud、NewsList、TickerSearch
  lib/              # API client
docs/               # 架構圖、模型比較報告、實驗設計說明
```

## 開發階段（對應申請表進度 A–H）

| Phase | 進度 | 內容 |
|---|---|---|
| 0 | — | 專案初始化、API 契約凍結 + mock endpoint |
| 1 | A | 資料集下載、清洗、去重、分層切分、分佈報告 |
| 2 | B | 基線模型（TF-IDF + LogReg / SVM），取得基準 Macro F1 |
| 3 | C | DistilBERT / BERT / RoBERTa fine-tuning 與比較表 |
| 4 | D | 最佳模型選定與超參數調整 |
| 5 | E | FastAPI 後端（新聞擷取 + 情緒推論） |
| 6 | F | Next.js 前端（情緒指針、關鍵字雲、新聞列表） |
| 7 | G | 前後端整合、端對端與異常情境驗證 |
| 8 | H | 技術文件與專題報告 |

## 啟動方式

```powershell
# 後端骨架（可立即執行）
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest                                   # 全部測試應通過
uvicorn newssent.api.main:app --reload   # 啟動 API

# NewsAPI 金鑰（/news 需要；/sentiment、/health mock 免金鑰）
copy .env.example .env                    # 編輯 .env 填入 NEWSAPI_KEY

# 前端（Phase 6，規劃中）
cd frontend && npm install && npm run dev
```

**分階段安裝重相依**（骨架階段不裝）：Phase 2 `pip install scikit-learn`；
Phase 3 依本機 CUDA 版本 `pip install torch --index-url .../cu121` 再 `pip install transformers datasets`。
Phase 3 前先確認 `python -c "import torch; print(torch.cuda.is_available())"` 為 `True`。

環境需求：Python 3.11+、Node 18+、NVIDIA GPU（Phase 3 訓練用）、NewsAPI 金鑰（放 `backend/.env`，勿進版控）。

## 團隊

指導老師：林逸程（財金系）
成員：資工 3 人（模型訓練管線／後端／前端）＋財金 2 人（情緒指標定義與金融解讀／線上抽測標注／報告撰寫）

> 免責聲明：本系統之情緒指標僅供學術研究與參考，不構成任何投資建議。
