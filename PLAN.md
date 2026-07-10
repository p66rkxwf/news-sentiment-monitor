# 基於自然語言處理之新聞情緒分析與即時監控系統 — 完整開發計畫

## Context（背景）

彰師大 115 年百萬專題探索申請案（跨域整合類，資工×財金 5 人團隊，指導老師林逸程），目標參加資訊應用服務創新競賽／全國大專院校產學創新實作競賽。申請表已定義技術棧與 A–H 八項學習進度，本計畫將其落實為可執行的開發藍圖，從零建置整個系統。

**已確認需求：**
- 分析範圍：**英文財經新聞＋美股代號**（如 AAPL、TSLA），與訓練資料語言一致；台股中文新聞列為未來延伸方向
- 訓練資料：**Financial PhraseBank**（sentences_50agree，約 4,846 筆標注句，對應申請表「約 4,840 筆」）
- 即時新聞來源：**NewsAPI**（申請表指定），以介面隔離並準備備援源
- 模型比較：TF-IDF + Logistic Regression、SVM（基線）→ DistilBERT、BERT、RoBERTa（fine-tuning），比較 Accuracy、Macro F1、推論速度
- 訓練環境：**本機 Windows 11 + NVIDIA GPU（PyTorch CUDA）**
- 技術棧（依申請表）：Hugging Face transformers、scikit-learn、FastAPI、Next.js

## 架構原則

以下五條原則貫穿整份計畫（沿用 stock-trend-assistant 已驗證的模式，改造為 NLP 場景），是 5 人分工不互相踩腳、模型與服務不脫節的地基：

1. **單一 Python package**：`ml/` 與 `api/` 不是平行頂層目錄，而是同一個可安裝 package `newssent/`（`pip install -e .`）內的子模組，根治 import 路徑問題（uvicorn 與 pytest 啟動路徑一致）。
2. **新聞來源藏在介面後**：所有即時新聞存取只透過 `NewsProvider` 介面，內建「先查快取→過期才連網→連網失敗退回快取」的降級策略。推論、測試都只認識這個介面（測試注入 FakeProvider，不打網路）。NewsAPI 免費層有每日 100 requests 與文章延遲 24 小時的限制，介面化讓備援源（yfinance news、Finnhub 免費層，皆近即時）可無痛切換或混用。
3. **訓練產物有版本契約**：模型存檔時一併寫入 `metadata.json`（模型名稱、tokenizer 名稱、max_length、**標籤順序**、資料切分 seed 與比例、訓練日期、測試指標）。API 啟動時比對，不一致就拒絕啟動——殺掉「標籤順序錯位後默默輸出相反情緒」這一整類無錯誤訊息的 bug。
4. **文字前處理單一入口**：`clean_text()` 是訓練與推論唯一共用進入點（transformers 的 tokenizer 綁定於模型本身，skew 風險集中在清洗規則與標籤映射，全部收進此入口），並以 parity 測試保證兩條路徑逐值相等。
5. **設定單一事實來源**：PhraseBank agreement 等級、標籤映射（negative/neutral/positive 的索引順序）、切分比例與 random seed、新聞快取 TTL、情緒指數公式參數，全部集中在 `config.py`。

## 專案結構

```
news-sentiment-monitor/
├── backend/
│   ├── pyproject.toml              # 以 package 安裝（pip install -e .），根治 import 問題
│   ├── requirements.txt            # 依賴鎖定
│   ├── newssent/                   # 單一 package（訓練與服務共用）
│   │   ├── config.py               # 唯一設定來源：agreement 等級、標籤順序、切分 seed、快取 TTL、指數公式參數
│   │   ├── data/
│   │   │   ├── phrasebank.py       # Financial PhraseBank 下載/解析/清洗/去重/分層切分（進度 A）
│   │   │   ├── provider.py         # NewsProvider 介面 + NewsAPIProvider（含快取與失敗降級）+ 備援 Provider
│   │   │   └── cache.py            # SQLite 新聞快取（key = ticker + 時間桶）
│   │   ├── text/
│   │   │   └── preprocess.py       # clean_text()：訓練/推論唯一共用入口
│   │   ├── ml/                     # 訓練管線（進度 A–D）
│   │   │   ├── dataset.py          # 去重後分層切分 70/15/15（固定 seed）、HF Dataset 轉換
│   │   │   ├── models/
│   │   │   │   ├── base.py         # 統一 predict_proba 介面（輸出順序固定 [neg, neu, pos]）
│   │   │   │   ├── baselines.py    # TF-IDF + LogisticRegression、LinearSVC（校準後輸出機率）
│   │   │   │   └── transformer.py  # DistilBERT/BERT/RoBERTa fine-tuning（HF Trainer、CUDA、fp16）
│   │   │   ├── train.py            # 統一訓練入口（--model tfidf_lr|svm|distilbert|bert|roberta）
│   │   │   ├── evaluate.py         # Accuracy、Macro F1、混淆矩陣、推論速度 benchmark（GPU/CPU 分列）
│   │   │   ├── compare.py          # 產出五模型比較表（Markdown + 圖）
│   │   │   └── registry.py         # artifact 存取 + metadata + 啟動一致性檢查
│   │   ├── inference/
│   │   │   ├── analyzer.py         # analyze(ticker)：抓新聞→clean_text→逐則情緒（吃 NewsProvider）
│   │   │   ├── aggregate.py        # 情緒指數：信心加權平均映射到 [−1, +1]（純函式，參數讀 config）
│   │   │   └── keywords.py         # 關鍵字雲：近期標題 TF-IDF 計分，去停用詞與公司名/代號
│   │   └── api/                    # FastAPI 服務（進度 E）
│   │       ├── main.py             # lifespan 載入模型、CORS、限流
│   │       ├── schemas.py          # Pydantic 回應模型（Phase 0 凍結）
│   │       ├── errors.py           # 統一錯誤回應格式與 status code
│   │       ├── deps.py             # ticker 格式驗證（FastAPI Depends，各 endpoint 共用）
│   │       └── routers/
│   │           ├── sentiment.py    # /api/stocks/{ticker}/sentiment、/api/stocks/{ticker}/news
│   │           └── meta.py         # /health、/api/model
│   ├── artifacts/                  # 模型權重（gitignore 大檔）；metadata.json 進版控
│   ├── data/                       # PhraseBank 原始檔與切分結果（原始檔 gitignore，切分索引進版控）
│   ├── news_cache.db               # SQLite 新聞快取（gitignore）
│   └── tests/                      # pytest
│       ├── test_preprocess.py      # clean_text 訓練/推論 parity
│       ├── test_split.py           # 去重後切分、無重複句跨集、seed 可重現
│       ├── test_aggregate.py       # 情緒指數公式邊界值（全正/全負/空清單）
│       └── test_api.py             # 注入 FakeProvider + 假模型，不打網路
├── frontend/                       # Next.js（進度 F，create-next-app + TypeScript + Tailwind）
│   ├── app/page.tsx                # 主監控儀表板
│   ├── components/
│   │   ├── SentimentGauge.tsx      # 情緒指針（−1 ~ +1，附指數說明與免責聲明）
│   │   ├── KeywordCloud.tsx        # 關鍵字雲（後端算分、前端渲染字級）
│   │   ├── NewsList.tsx            # 新聞列表（情緒標籤 + 信心分數 + 原文連結）
│   │   └── TickerSearch.tsx        # 美股代號輸入
│   └── lib/api.ts                  # 後端 API client
├── docs/                           # 進度 H：系統架構圖、模型比較報告、實驗設計說明
├── PLAN.md
└── README.md
```

另外執行 `git init` 建立版本控制，`.gitignore` 排除 `.venv`、`node_modules`、`artifacts/`（大檔）、`data/`（原始資料）、`news_cache.db`、`.env`（**NewsAPI 金鑰只放 `.env`，絕不進版控**）。

## 開發階段（對應申請表進度 A–H）

### Phase 0：專案初始化 + API 契約凍結

- `git init`、建立上述 `newssent/` package 骨架、`backend/.venv`、`pyproject.toml`（可 `pip install -e .`）、`requirements.txt`
- 關鍵相依：`torch`（CUDA wheel，依本機 CUDA 版本選擇）、`transformers`、`datasets`、`scikit-learn`、`fastapi`、`uvicorn`、`slowapi`（限流）、`python-dotenv`
- 環境自檢腳本：確認 `torch.cuda.is_available()` 為 True 再進 Phase 3，避免默默退回 CPU 訓練
- **凍結 API 契約（解鎖 5 人並行開發的關鍵）**：先寫定 `schemas.py` 與 `errors.py`，後端出**假資料 mock endpoint**，前端從第一週即可對接。錯誤格式統一為 `{"error": {"code": ..., "message": ...}}`：404 = 代號查無新聞、422 = 代號格式錯誤、503 = 新聞源失敗且無快取可退

### Phase 1（A）：資料集準備與探索

- `phrasebank.py` 下載 Financial PhraseBank，選用 `sentences_50agree`（約 4,846 筆，對應申請表數字；agreement 等級寫入 `config.py`，之後可比較 66/75agree 對品質的影響）
- **切分前先去重**：原始資料含重複句，不去重就切分會讓同一句同時出現在訓練與測試集，比較表數字全部虛高
- 分層（stratified）切分 70/15/15，固定 random seed，切分索引存檔進版控——**全隊用同一份切分**，模型比較才公平
- 產出 `docs/data_exploration.md`：類別分佈（neutral 約 6 成、positive 約 25%、negative 約 12%——嚴重不平衡，據此確立 **Macro F1 為主指標 + class weight**）、句長分佈（決定 max_length）、重複句統計（申請表要求的資料分佈統計報告）

### Phase 2（B）：基線模型

- TF-IDF（uni+bigram）+ Logistic Regression（class_weight='balanced'）
- TF-IDF + LinearSVC（以 CalibratedClassifierCV 校準，讓 SVM 也能輸出信心機率，與 API 契約一致）
- 兩模型皆走 `clean_text()` → `base.py` 統一 `predict_proba` 介面，輸出順序固定 [negative, neutral, positive]
- 記錄 Accuracy 與 Macro F1 作為基準——**transformer 模型必須明顯超越此基準才有部署價值**

### Phase 3（C）：Transformer 模型 fine-tuning

- DistilBERT（`distilbert-base-uncased`）、BERT（`bert-base-uncased`）、RoBERTa（`roberta-base`）三模型統一以 HF `Trainer` fine-tuning：CUDA、fp16、early stopping（驗證集 Macro F1）、class weight 處理不平衡
- max_length 依 Phase 1 句長分佈設定（PhraseBank 為短句，預估 64–128 即足，太長浪費視訊記憶體與時間）
- batch size 依 VRAM 調整；單一模型在本機 GPU 上預估數分鐘～十餘分鐘/epoch，全程可行
- **推論速度 benchmark 分 GPU 與 CPU 兩欄**（`evaluate.py`）：部署機有 GPU 時 BERT 也夠快，但若未來部署到無 GPU 環境，DistilBERT 的速度優勢才顯現——兩種場景在比較報告中都要呈現，這是申請表「推論速度比較」的完整答法
- `compare.py` 產出五模型比較表（Accuracy／Macro F1／GPU 推論 ms/句／CPU 推論 ms/句／模型大小），直接進 `docs/` 與專題報告

### Phase 4（D）：最佳模型選定與調參

- 對比較表最佳者做超參數搜尋（learning rate、epochs、warmup、max_length；用驗證集），確認測試集 Macro F1 穩定優於基線
- **選型標準文件化**：不只看分數，綜合「Macro F1 提升幅度 vs 推論成本」給出選型理由（這正是申請表預期成果「客觀的模型選型依據」）
- 最終模型 + tokenizer + `metadata.json` 經 `registry.py` 存入 `artifacts/`，供 API 載入；`metadata.json` 記錄標籤順序，API 啟動時比對 `config.py`，不一致拒絕啟動

### Phase 5（E）：FastAPI 後端 + 推論層

- **先建 `NewsProvider` 介面**：`get_news(ticker, limit) -> list[Article]`。`NewsAPIProvider` 實作並內建「先查 SQLite 快取→過期才連網→連網失敗退回快取（回應標記 `stale: true`）」
- **NewsAPI 免費層對策**（每日 100 requests、文章延遲 24h）：快取 key = ticker + 時間桶（如 1 小時），同 ticker 一小時內只打一次 API；備援 `YFinanceNewsProvider`（近即時、免金鑰）在 NewsAPI 額度用罄或延遲不可接受時切換，切換只動 `config.py` 一行
- `GET /api/stocks/{ticker}/sentiment`：抓新聞 → `clean_text` → 批次推論 → `aggregate.py` 計算情緒指數（信心加權：Σ(±1 × confidence) / n，映射 [−1, +1]，公式參數在 config 並文件化）→ 回傳 `{score, label, article_count, keywords, model_version, as_of}`
- `GET /api/stocks/{ticker}/news`：逐則新聞附 `{title, url, published_at, sentiment, confidence}`
- 補兩支便宜 endpoint：`GET /health`（模型是否載入成功，demo 前自檢）、`GET /api/model`（版本、訓練日、測試 Macro F1）
- ticker 驗證放 `deps.py`（`Depends`）：正規 `^[A-Z]{1,5}(\.[A-Z])?$`，防路徑穿越（ticker 會進快取 key）；`slowapi` 每 IP 限流（保護 NewsAPI 每日額度不被單一使用者吃光）；CORS 明確 origin 清單，勿用 `*`
- 關鍵字雲：`keywords.py` 對近期標題做 TF-IDF 計分，停用詞 + 公司名/代號本身要剔除（否則每檔股票的關鍵字雲都被自己的名字佔滿）

### Phase 6（F）：Next.js 前端

- `create-next-app`（TypeScript + Tailwind）
- 主頁：代號搜尋 → **情緒指針**（半圓儀表 −1 ~ +1，紅綠依美股慣例：漲綠/跌紅，與台股相反，需在 UI 明示）＋**關鍵字雲**（後端給分數、前端映射字級，不引入重型繪圖庫）＋**新聞列表**（情緒標籤色塊 + 信心分數 + 連結原文）
- 顯示 `as_of` 時間戳與 `stale` 標記（快取降級時使用者要知道資料非最新）＋投資免責聲明

### Phase 7（G）：整合與端對端驗證

- 驗證 Phase 0 凍結的錯誤契約：無效代號（422）、查無新聞（404）、新聞源失敗有快取（200 + stale）、新聞源失敗無快取（503）、載入狀態
- 端對端流程：輸入 AAPL → 指針、關鍵字雲、新聞列表正確對應顯示；確認前後端錯誤處理一致
- **對即時新聞做人工抽測**：隨機抽 30 則線上標題人工標注，與模型輸出比對——PhraseBank（分析師標注短句）與實際新聞標題存在分佈落差，抽測結果誠實寫入報告的限制章節

### Phase 8（H）：文件

- `docs/`：系統架構圖（mermaid）、五模型比較報告（含 GPU/CPU 速度兩欄）、實驗設計說明（去重、分層切分、class weight 的理由）、線上抽測結果與限制討論、README 安裝執行指南——直接可用於專題報告與競賽文件

## 關鍵技術決策與風險

| 項目 | 決策 | 理由 |
|---|---|---|
| PhraseBank agreement 等級 | 50agree（約 4,846 筆） | 對應申請表數字；樣本最多；等級寫入 config 可後續比較 |
| 切分洩漏 | **去重後才分層切分**，切分索引進版控 | 重複句跨集會讓全部模型分數虛高，比較表失真 |
| 類別不平衡 | Macro F1 主指標 + class weight | neutral 過半，Accuracy 會被「全猜 neutral」灌水 |
| SVM 機率輸出 | CalibratedClassifierCV 校準 | API 契約要求信心分數，LinearSVC 原生無機率 |
| **NewsAPI 免費層限制** | **Provider 介面 + 時間桶快取 + yfinance 備援** | **每日 100 requests、延遲 24h 會讓 demo 當場斷線；介面化讓切換零成本，雜支預算含訂閱費可升級** |
| **標籤順序錯位** | **metadata.json 記錄順序 + 啟動比對** | **順序錯位不報錯、只默默輸出相反情緒，5 人分工幾乎必然踩到** |
| **訓練/推論一致** | **clean_text() 單一入口 + parity 測試** | **training/serving skew 是產線 ML 最隱蔽的 bug** |
| 分佈落差 | 線上標題人工抽測 + 報告限制章節 | PhraseBank 是分析師標注短句，與即時新聞標題風格不同；誠實呈現比隱藏更有競賽說服力 |
| 推論速度比較 | GPU/CPU 兩欄分列 | 部署場景不同結論不同；單一數字會誤導選型 |
| API 金鑰 | 只放 `.env`（gitignore） | NewsAPI 金鑰進版控 = 洩漏，額度被盜用 |
| **範圍克制** | **不做 Docker/MQ/正式 DB/使用者系統/串流推播** | **競賽專題規模，SQLite + 輪詢即足夠；過度基礎設施是負債** |

## 安全性與合規（本機 demo 範圍）

不做登入/授權/角色系統（正確的範圍克制），但以下四點即使 demo 也處理：

1. **ticker 輸入驗證**：`^[A-Z]{1,5}(\.[A-Z])?$` 正規驗證，防路徑穿越與注入（ticker 會進快取 key 與外部 API query）
2. **限流**：`slowapi` 每 IP 限流，保護 NewsAPI 每日 100 requests 額度
3. **CORS**：明確 origin 清單，勿 `allow_origins=["*"]`
4. **投資免責聲明**：UI 與 API 回應皆含免責聲明（情緒指標非投資建議）

## 驗證方式

1. `pytest backend/tests/`：clean_text parity、切分無重複跨集且 seed 可重現、情緒指數邊界值、API 回應格式（注入 FakeProvider 與假模型，不打網路）
2. 訓練管線煙霧測試：以 500 筆子集跑通 `train.py` 全部五種模型
3. **artifact 契約測試**：故意改動 config 標籤順序，確認 API 啟動時如期拒絕載入
4. `uvicorn newssent.api.main:app` 啟動後端，curl 驗證 `/sentiment`、`/news`、`/health`、`/api/model` 回應
5. `npm run dev` 啟動前端，瀏覽器實測輸入 AAPL 端對端顯示指針＋關鍵字雲＋新聞列表
6. 完整訓練跑完後檢查 `compare.py` 比較表：transformer 模型 Macro F1 應明顯高於基線（PhraseBank 上 fine-tuned BERT 類模型文獻表現約 0.85–0.95，基線約 0.70–0.80，落在此區間屬合理）
7. 拔網路測試快取降級：斷網後 `/sentiment` 應回傳快取結果 + `stale: true`，而非 500

## 執行順序建議

**第一週的地基（做對成本最低、事後改成本最高）：**

1. **單一 package + `pyproject.toml`** — 目錄骨架是所有程式碼的地基，事後搬目錄要改遍 import
2. **去重 + 固定切分索引** — 必須在第一個模型訓練前就位，否則所有已跑實驗數字作廢重跑
3. **API 契約凍結 + mock endpoint** — 5 人分工的解鎖鍵，晚一週定前端就閒置一週
4. **metadata + 標籤順序啟動檢查** — 必須在 Phase 4 存檔前就位；`base.py` 統一輸出順序從第一個基線模型就遵守
5. **NewsProvider 介面 + 快取** — Phase 5 才用到，但介面先定好，FakeProvider 讓 API 測試從第一天可寫

**批次順序：** Phase 0–2 為第一批（地基＋資料＋基線，約佔工作量 35%），Phase 3–4 第二批（transformer 訓練與選型），Phase 5–7 第三批（系統整合），Phase 8 收尾。每個 Phase 完成即 git commit。因 API 契約在 Phase 0 已凍結，前端可在第一批期間即以 mock 並行開發。

**5 人分工建議：** 資工 3 人 — 模型訓練管線（Phase 1–4）、FastAPI 後端＋推論層（Phase 5）、Next.js 前端（Phase 6）；財金 2 人 — 情緒指數公式定義與金融解讀、線上抽測標注與限制分析、標的選擇與報告撰寫。財金成員的人工抽測與指標解讀正是「跨域整合類」的加分核心。
