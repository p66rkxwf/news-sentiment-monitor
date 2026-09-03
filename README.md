# 基於自然語言處理之新聞情緒分析與即時監控系統

彰師大 115 年百萬專題探索（跨域整合類）。透過 NLP 技術自動擷取美股財經新聞並即時分析市場情緒，將非結構化文字轉化為可量化的情緒指標，輔助投資決策。

> 完整開發計畫見 [PLAN.md](PLAN.md)。**全部 Phase（0–8）已完成**：五模型比較後選型
> fine-tuned **BERT**（測試 Macro F1 **0.8458**，基線 0.7286），FastAPI 真實推論、
> yfinance 即時新聞源（含快取降級）、Next.js 監控儀表板、線上抽測與完整文件。

> **現行 production 模型為 `bert-combined`**（2026-08-14 起）。財金組獨立複核揭露
> 「抓不到負面、過度給方向」後，診斷為**任務定義錯誤**——量的是句子語氣，
> 該量的是「這則標題對**這支股票**是好消息還是壞消息」，故改以
> PhraseBank＋SEntFiN 合併語料重訓目標導向模型（[實驗 #6](docs/experiment_target_sentiment.md)）。
> 換模型的理由是任務定義，**不是分數**——#6 那 15 個百分點在 2026-09-03 的
> [確認實驗](docs/confirmation_2026-09-03.md)中**沒有複製出來**，我們照事先寫死的
> 預先聲明記為一次失敗的確認。引用本專案任何一致率數字時，請一併看那份確認結果。

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
| 訓練資料 | Financial PhraseBank（sentences_50agree，4,846 筆標注句）＋ SEntFiN 1.0（10,753 則標題，實體層級標注）|
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
  tools/            # spot_check.py（抽測取樣/盲標表）、compare_arms.py（方案對照＋McNemar）、
                    # contamination_check.py（預訓練污染）、timestamp_lag.py（時間戳落差）
  tests/            # pytest 81 項（FakeProvider，不打網路；含 pytest -m leakage 洩漏防治 18 項）
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

### 第二輪（2026-08~09）任務定義修正與確認實驗

| 主題 | 結果 |
|---|---|
| 財金組獨立盲標複核（3 批共 120 則） | 揭露「抓不到負面、過度給方向」；**AI 自標 66.7% vs 人工 46.7%**，證實自己標自己的考卷會高估 |
| 實驗 #6：語氣 → 對該標的的方向 | 一致率 46.7%→61.7%（**候選結論**）；production 改 `bert-combined` |
| **預先聲明 + 確認實驗** | 新批 60 則盲標：60.0% vs 63.3%，**p=0.804，H1 未獲確認**——15pp 沒有複製，誠實記為失敗 |
| 資料誠信（洩漏／污染／時間戳） | 打亂標籤測試、735 則線上標題 0 近重複、發布→抓取落差中位數 2.94 小時 |

> 確認實驗失敗後 production **維持** `bert-combined`：兩者統計上無法區分，
> 用無法區分的差距換模型等於拿噪音當決策依據；當初換模型的理由是任務定義而非分數。
> 但**不再宣稱一致率提升**。

## 啟動方式

```powershell
# 後端
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128   # NVIDIA GPU
pip install -e ".[dev]"
pytest                                    # 81 項測試應全部通過
pytest -m leakage                         # 18 項洩漏防治（pre-push 閘門跑的就是這組）
powershell -File ../scripts/install_hooks.ps1   # 安裝 pre-push 閘門（測不過不准 push）
uvicorn newssent.api.main:app --port 8001 # 啟動 API（:8000 讓給 stock 專案）

# 前端
cd frontend && npm install && npm run dev  # http://localhost:3000
```

訓練與比較：

```powershell
cd backend
python -m newssent.ml.train --model bert --corpus combined   # 語料 phrasebank|sentfin|combined
python -m newssent.ml.tune  --model bert   # 超參數搜尋（lr × max_length）
python -m newssent.ml.compare              # 產出 docs/model_comparison.md
python tools/spot_check.py sample          # 線上抽測取樣（人工標注後跑 report）
python tools/compare_arms.py --no-llm --samples ../docs/<批次>.csv --out ../docs/<報告>.md
python tools/contamination_check.py        # 預訓練污染分析
python tools/timestamp_lag.py              # 發布→抓取時間落差實測
```

新聞來源預設 **yfinance（免金鑰）**；取得 NewsAPI 金鑰後：`copy .env.example .env`
填入 `NEWSAPI_KEY`，並把 `newssent/config.py` 的 `NEWS_PROVIDER` 改回 `"newsapi"`。

環境需求：Python 3.11+、Node 18+、NVIDIA GPU（訓練用；推論 CPU 亦可，見比較表速度欄）。

## 文件索引

- **方法論**：[預先聲明](docs/preregistration_2026-08-14.md)（假說與裁決規則事先定死）、
  [確認實驗結果](docs/confirmation_2026-09-03.md)（H1 未獲確認，誠實記為失敗）、
  [預訓練污染分析](docs/pretraining_contamination.md)、[時間戳語意](docs/timestamp_semantics.md)
- **實驗**：[實驗 #6 任務定義修正](docs/experiment_target_sentiment.md)（候選結論，含警語）、
  [模型比較](docs/model_comparison.md)、[選型依據](docs/model_selection.md)、[實驗設計](docs/experiment_design.md)
- **線上抽測**：[財金組複核](docs/online_spot_check.md)、[07-17 批](docs/online_spot_check_2026-07-17.md)
- **系統**：[架構](docs/architecture.md)、[資料探索](docs/data_exploration.md)、[SEntFiN 語料](docs/data_exploration_sentfin.md)

## 團隊

指導老師：林逸程（財金系）
成員：資工 3 人（模型訓練管線／後端／前端）＋財金 2 人（情緒指標定義與金融解讀／線上抽測標注／報告撰寫）

> 免責聲明：本系統之情緒指標僅供學術研究與參考，不構成任何投資建議。
