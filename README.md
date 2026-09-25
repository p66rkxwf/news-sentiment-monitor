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
使用者（手機或電腦）
        │
        ▼
 Next.js 分頁式 App ──/api/* 轉送──► FastAPI 後端 ──► NewsProvider（yfinance 主源 + 快取降級）
   · 總覽：新聞刻度帶                 │                 └► BERT 情緒分類（bert-combined）
   · 新聞／追蹤清單                   │
   · 台股預警 ◄───────────────────────┴──► 預警分數庫（alert_recorder 離線寫入：FinMind 中文新聞 + LLM 評分）
   · 設定（主題、模型資訊）
```

前端是可以「加到主畫面」的 PWA：手機是底部分頁列、電腦是左側欄，預設深色。

## 技術棧

| 層 | 技術 |
|---|---|
| 訓練資料 | Financial PhraseBank（sentences_50agree，4,846 筆標注句）＋ SEntFiN 1.0（10,753 則標題，實體層級標注）|
| 即時新聞 | yfinance news（主源，免金鑰）、NewsAPI（`config.NEWS_PROVIDER` 一行切換） |
| 基線模型 | TF-IDF + Logistic Regression、TF-IDF + SVM |
| 深度模型 | DistilBERT / BERT / RoBERTa fine-tuning（PyTorch CUDA + Hugging Face） |
| 台股預警 | FinMind 中文新聞（事後回補）＋ 本機 LLM `gemma3:27b` 評分，z 值對 20 日基準 |
| 後端 | FastAPI（Python，單一 package `newssent/`） |
| 前端 | Next.js 16 + TypeScript + Tailwind v4；分頁式 App、PWA（manifest＋圖示，無離線快取） |
| 評估指標 | Accuracy、Macro F1、推論速度（GPU/CPU 分列） |

## 目錄導覽

```
backend/
  newssent/         # 單一 Python package（訓練與 API 服務共用）
    config.py       # 唯一設定來源（標籤順序、切分 seed、快取 TTL…）
    data/           # PhraseBank 處理、NewsProvider 介面（yfinance/NewsAPI）、新聞快取
    text/           # clean_text()：訓練/推論唯一共用前處理入口
    ml/             # 五模型訓練、調參、評估、比較、artifact registry
    inference/      # ticker→新聞→情緒→彙總指數→關鍵字；台股預警（alerts、alert_board、alert_recorder）
    api/            # FastAPI routers、schemas、錯誤契約
  artifacts/        # 模型權重與 metadata.json（權重 gitignore）
  data/             # 資料集原始檔與切分索引
  tools/            # spot_check.py（抽測取樣/盲標表）、compare_arms.py（方案對照＋McNemar）、
                    # contamination_check.py（預訓練污染）、timestamp_lag.py（時間戳落差）、
                    # alert_backtest.py（預警歷史回測）、judge_qualify.py（Codex 裁判資格考）
  tests/            # pytest 152 項（FakeProvider，不打網路；含 pytest -m leakage 洩漏防治 18 項）
frontend/
  app/              # 五個分頁：/ 總覽、/news、/watchlist、/alerts、/settings；manifest 與圖示
  components/       # AppShell（分頁列／側欄）、SentimentScale（新聞刻度帶）、NewsList、AlertCard…
  lib/              # API client（對應 Phase 0 凍結契約）、跨分頁共用狀態 app-state
docs/               # 架構圖、模型比較/選型、實驗設計、線上抽測、資料探索、預警回測
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

### 第三輪（2026-09）台股情緒預警與前端 App 化

| 主題 | 結果 |
|---|---|
| 台股情緒異常預警（`/api/alerts`） | 49 檔台股、FinMind 中文新聞、LLM 評分；當日分數對前 20 個交易日的 z 值，z < −1.5 留意、z < −2 高度異常 |
| 預先聲明的歷史回測（[報告](docs/alert_backtest.md)） | 21 件大跌事件，事前 5 日內示警 4/17，與隨機響鈴無法區分（**p = 0.983**）——**不得宣稱「提前預警」**，只呈現開盤前的即時示警與證據標題 |
| 前端改為分頁式 App | 總覽／新聞／追蹤／預警／設定；手機底部分頁列、電腦左側欄；可加到主畫面（PWA） |

## 啟動方式

```powershell
# 後端
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cu128   # NVIDIA GPU
pip install -e ".[dev]"
pytest                                    # 152 項測試應全部通過
pytest -m leakage                         # 18 項洩漏防治（pre-push 閘門跑的就是這組）
powershell -File ../scripts/install_hooks.ps1   # 安裝 pre-push 閘門（測不過不准 push）
uvicorn newssent.api.main:app --port 8001 # 啟動 API（:8000 讓給 stock 專案）

# 前端
cd frontend && npm install && npm run dev  # http://localhost:3000
```

**前端怎麼連後端**：瀏覽器只連前端，`/api/*` 由 Next 轉送到 `http://127.0.0.1:8001`
（改用環境變數 `API_PROXY_TARGET`）。後端不必開在區網、也不必改 CORS。

**用手機看（demo）**：手機和電腦連同一個 Wi-Fi，然後：

```powershell
cd frontend
npm run build; npm start                   # 正式模式，手機開 http://<電腦的區網 IP>:3000
# 若要用 dev 模式：$env:DEV_ORIGINS="192.168.x.x"; npm run dev
```

- iPhone Safari →「分享」→「加入主畫面」，之後從主畫面開就是全螢幕、沒有網址列。
- Android Chrome 只有在 HTTPS 或 localhost 下才會以 App 形式安裝；區網 http 只會是一般捷徑（開在瀏覽器裡）。
- **限流是共用的**：後端每個 IP 每分鐘 30 次、所有端點合計；經 Next 轉送後所有裝置都算同一個 IP。
  前端已把資料快取在本次開啟內（切分頁不重抓），單人 demo 夠用；多台裝置同時操作可能看到「查詢太頻繁」。
- 預警分頁的資料來自 `backend/alert_scores.db`，要看最新交易日得先跑 `python -m newssent.inference.alert_recorder`；
  沒跑的話預設日期會顯示「資料不足」，用日期切換看歷史交易日即可。

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
- **台股預警**：[回測預先聲明](docs/alert_backtest_prereg.md)、[回測結果](docs/alert_backtest.md)（p = 0.983，不得宣稱提前預警）、
  [Codex 裁判資格考預先聲明](docs/judge_qualification_prereg.md)（合格標準 strict，尚待執行）
- **實驗**：[實驗 #6 任務定義修正](docs/experiment_target_sentiment.md)（候選結論，含警語）、
  [模型比較](docs/model_comparison.md)、[選型依據](docs/model_selection.md)、[實驗設計](docs/experiment_design.md)
- **線上抽測**：[財金組複核](docs/online_spot_check.md)、[07-17 批](docs/online_spot_check_2026-07-17.md)
- **系統**：[架構](docs/architecture.md)、[資料探索](docs/data_exploration.md)、[SEntFiN 語料](docs/data_exploration_sentfin.md)

## 團隊

指導老師：林逸程（財金系）
成員：資工 3 人（模型訓練管線／後端／前端）＋財金 2 人（情緒指標定義與金融解讀／線上抽測標注／報告撰寫）

> 免責聲明：本系統之情緒指標僅供學術研究與參考，不構成任何投資建議。
