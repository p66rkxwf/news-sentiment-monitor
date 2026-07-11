# 基於自然語言處理之新聞情緒分析與即時監控系統

彰師大 115 年百萬專題探索（跨域整合類）。透過 NLP 技術自動擷取美股財經新聞並即時分析市場情緒，將非結構化文字轉化為可量化的情緒指標，輔助投資決策。

> 完整開發計畫見 [PLAN.md](PLAN.md)。**全部 Phase（0–8）已完成**：五模型比較後選型
> fine-tuned **BERT**（測試 Macro F1 **0.8458**，基線 0.7286），FastAPI 真實推論、
> yfinance 即時新聞源（含快取降級）、Next.js 監控儀表板、線上抽測與完整文件。

## 系統概觀

```
使用者輸入股票代號（如 AAPL）
        │
        ▼
 Next.js 前端儀表板 ──► FastAPI 後端 ──► NewsProvider（yfinance 主源 + 快取降級）
   · 情緒指針                │
   · 關鍵字雲                ▼
   · 新聞情緒列表      BERT 情緒分類（五模型比較選出，見 docs/model_selection.md）
```

## 技術棧

| 層 | 技術 |
|---|---|
| 訓練資料 | Financial PhraseBank（sentences_50agree，4,846 筆標注句） |
| 即時新聞 | yfinance news（主源，免金鑰）、NewsAPI（`config.NEWS_PROVIDER` 一行切換） |
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
    data/           # PhraseBank 處理、NewsProvider 介面（yfinance/NewsAPI）、新聞快取
    text/           # clean_text()：訓練/推論唯一共用前處理入口
    ml/             # 五模型訓練、調參、評估、比較、artifact registry
    inference/      # ticker→新聞→情緒→彙總指數→關鍵字
    api/            # FastAPI routers、schemas、錯誤契約
  artifacts/        # 模型權重與 metadata.json（權重 gitignore）
  data/             # 資料集原始檔與切分索引
  tools/            # spot_check.py：線上標題人工抽測
  tests/            # pytest 51 項（FakeProvider，不打網路）
frontend/
  app/              # Next.js 主頁（stale 徽章、as_of、免責聲明）
  components/       # SentimentGauge、KeywordCloud、NewsList、TickerSearch
  lib/              # API client（對應 Phase 0 凍結契約）
docs/               # 架構圖、模型比較/選型、實驗設計、線上抽測、資料探索
```

## 開發階段（對應申請表進度 A–H）— 全部完成

| Phase | 進度 | 內容 | 狀態 |
|---|---|---|---|
| 0 | — | 專案初始化、API 契約凍結 + mock endpoint | ✅ |
| 1 | A | 資料集下載、清洗、去重、分層切分、分佈報告 | ✅ |
| 2 | B | 基線模型（TF-IDF + LogReg / SVM），基準 Macro F1 0.72 | ✅ |
| 3 | C | DistilBERT / BERT / RoBERTa fine-tuning 與比較表（GPU/CPU 兩欄） | ✅ |
| 4 | D | 調參 + 選型 **BERT**（[選型依據](docs/model_selection.md)） | ✅ |
| 5 | E | FastAPI 後端（yfinance 新聞 + BERT 推論 + 快取降級） | ✅ |
| 6 | F | Next.js 前端（情緒指針、關鍵字雲、新聞列表） | ✅ |
| 7 | G | 端對端驗證 + [30 則線上抽測](docs/online_spot_check.md) | ✅ |
| 8 | H | 技術文件（[架構](docs/architecture.md)、[實驗設計](docs/experiment_design.md)、[模型比較](docs/model_comparison.md)） | ✅ |

## 啟動方式

```powershell
# 後端
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128   # NVIDIA GPU
pip install -e ".[dev]"
pytest                                    # 51 項測試應全部通過
uvicorn newssent.api.main:app --port 8001 # 啟動 API（:8000 讓給 stock 專案）

# 前端
cd frontend && npm install && npm run dev  # http://localhost:3000
```

訓練與比較：

```powershell
cd backend
python -m newssent.ml.train --model bert   # tfidf_lr|svm|distilbert|bert|roberta
python -m newssent.ml.tune  --model bert   # 超參數搜尋（lr × max_length）
python -m newssent.ml.compare              # 產出 docs/model_comparison.md
python tools/spot_check.py sample          # 線上抽測取樣（人工標注後跑 report）
```

新聞來源預設 **yfinance（免金鑰）**；取得 NewsAPI 金鑰後：`copy .env.example .env`
填入 `NEWSAPI_KEY`，並把 `newssent/config.py` 的 `NEWS_PROVIDER` 改回 `"newsapi"`。

環境需求：Python 3.11+、Node 18+、NVIDIA GPU（訓練用；推論 CPU 亦可，見比較表速度欄）。

## 團隊

指導老師：林逸程（財金系）
成員：資工 3 人（模型訓練管線／後端／前端）＋財金 2 人（情緒指標定義與金融解讀／線上抽測標注／報告撰寫）

> 免責聲明：本系統之情緒指標僅供學術研究與參考，不構成任何投資建議。
