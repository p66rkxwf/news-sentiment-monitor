"""唯一設定來源：標籤順序、切分 seed/比例、快取 TTL、情緒指數公式參數等。

不要在 text/、ml/、api/、frontend 各自維護副本——一律從這裡讀取。
標籤順序尤其關鍵：negative/neutral/positive 的索引順序一旦與訓練時錯位，
模型會不報錯地輸出相反情緒；registry 啟動檢查會以此處的順序為準（Phase 4）。
"""

import os
import shutil
import tempfile
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # 讀取 backend/.env（若存在）


def _fix_curl_ca_bundle() -> None:
    """專案路徑含非 ASCII 字元（如「百萬專題」）時，libcurl 讀不到 venv 內
    certifi 的 CA 檔（curl error 77），yfinance/curl_cffi 的所有 HTTPS 都會失敗。
    對策：把 cacert.pem 複製到 ASCII 路徑並以 CURL_CA_BUNDLE 指定（已設定者不動）。
    """
    if os.environ.get("CURL_CA_BUNDLE"):
        return
    try:
        import certifi

        src = certifi.where()
        if src.isascii():
            return  # 路徑本來就沒問題
        base = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
        if not base.isascii():
            return  # 找不到 ASCII 落腳處，維持原行為（快取降級仍可運作）
        target = Path(base) / "newssent" / "cacert.pem"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.stat().st_size != Path(src).stat().st_size:
            shutil.copyfile(src, target)
        os.environ["CURL_CA_BUNDLE"] = str(target)
    except Exception:
        pass  # 盡力而為，不因此擋住啟動


_fix_curl_ca_bundle()

BACKEND_ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = BACKEND_ROOT / "artifacts"
DATA_DIR = BACKEND_ROOT / "data"
NEWS_CACHE_DB_PATH = BACKEND_ROOT / "news_cache.db"

# --- 標籤（固定順序，全流程共用）---
LABEL_NAMES: list[str] = ["negative", "neutral", "positive"]
LABEL_TO_ID: dict[str, int] = {name: i for i, name in enumerate(LABEL_NAMES)}
# 情緒指數的極性符號：neutral 不貢獻極性
SENTIMENT_SIGN: dict[str, int] = {"negative": -1, "neutral": 0, "positive": 1}

# --- 資料集（Phase 1）---
PHRASEBANK_AGREEMENT = "50agree"        # 約 4,846 筆；可改 66/75agree 比較品質
SPLIT_SEED = 42
SPLIT_RATIOS: tuple[float, float, float] = (0.70, 0.15, 0.15)  # train/val/test
MAX_LENGTH = 128                        # Phase 1 依句長分佈最終確認

# --- 模型（Phase 4 選型；2026-08-14 實驗 #6 換任務定義）---
# 2026-07-11 五模型比較（驗證集 Macro F1 選型，避免用測試集挑模型的樂觀偏差）：
#   bert(調參後 lr=2e-5, max_length=64) 0.8542 > distilbert 0.8395 > roberta 0.8451
#   > tfidf_lr 0.7121 > svm 0.7079；測試集確認 bert 0.8458 仍居首
# 2026-08-14 實驗 #6：財金組複核暴露的錯誤（抓不到負面、過度給方向）根因是**任務定義**——
#   PhraseBank 量的是語氣，線上要答的是「這則標題對這支股票是好是壞」。改用
#   PhraseBank＋SEntFiN 合併語料訓練的**目標導向**模型（輸入為 (公司名, 標題) 配對），
#   在 60 則財金組標注上一致率 46.7%→61.7%（McNemar p=0.035，未過多重比較修正）。
#   完整比較與誠實邊界見 docs/experiment_target_sentiment.md。
PRODUCTION_MODEL = "bert-combined"      # artifacts/<名稱>/，由 compare.py 結果決定

# --- 目標導向推論（實驗 #6）---
# 目標導向模型的輸入是 (目標實體, 標題)，但線上只拿得到 ticker，而新聞標題裡寫的是
# 公司名。這份對照表把 ticker 還原成訓練語料中會出現的實體字串；查無對照時退回
# ticker 本身（模型仍可運作，只是少了名稱線索）。
TICKER_COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple",
    "TSLA": "Tesla",
    "NVDA": "Nvidia",
    "MSFT": "Microsoft",
    "GOOG": "Google",
    "GOOGL": "Google",
    "AMZN": "Amazon",
    "META": "Meta",
    "AMD": "AMD",
    "INTC": "Intel",
    "TSM": "TSMC",
    "MU": "Micron",
    "NFLX": "Netflix",
    "AVGO": "Broadcom",
    # 2026-09 靜態站固定清單（STATIC_TICKERS）新增的公司；ETF（QQQ、SPY）沒有單一公司實體，維持以代號當目標
    "QCOM": "Qualcomm",
    "ORCL": "Oracle",
    "ADBE": "Adobe",
    "CRM": "Salesforce",
    "ASML": "ASML",
    "ARM": "Arm",
    "UMC": "UMC",
    "ASX": "ASE Technology",
    "CHT": "Chunghwa Telecom",
}

# --- 靜態站（news.sekinv.com）每日預先計算的標的 ---
# 公開站沒有常駐後端，只能提供事先算好的清單；前端搜尋改為從此清單挑選。
# TSM/UMC/ASX/CHT/QQQ 是 stock-trend-assistant 情緒卡的 ADR 對照與大盤代理（其 lib/newsApi.ts），不可移除。
STATIC_TICKERS: tuple[str, ...] = (
    "AAPL", "MSFT", "NVDA", "GOOG", "AMZN", "META", "TSLA", "AVGO", "AMD", "INTC", "MU", "NFLX",
    "QCOM", "ORCL", "ADBE", "CRM", "ASML", "ARM", "TSM", "UMC", "ASX", "CHT", "QQQ", "SPY",
)


def company_name(ticker: str) -> str:
    return TICKER_COMPANY_NAMES.get((ticker or "").upper(), ticker)


# --- 情緒指數（Phase 5 aggregate.py）---
# score = Σ(sign × confidence) / n，映射 [−1, +1]；|score| 超過門檻才判為正/負，否則中性
SENTIMENT_LABEL_THRESHOLD = 0.15

# --- 情緒異常預警（inference/alerts.py）---
# 規則：當日分數比前 20 個交易日平均低超過 1.5σ → watch、超過 2σ → high。
# 下列門檻必須在看回測結果**之前**定案（見 docs/alert_backtest_prereg.md）；
# 看完事件結果再回頭調，回測就只是在描述我們挑過的樣本。
ALERT_WINDOW_SESSIONS = 5        # 近期趨勢展示窗
ALERT_BASELINE_SESSIONS = 20     # 常態基準窗（不含當日）
ALERT_WATCH_Z = -1.5
ALERT_HIGH_Z = -2.0
ALERT_MIN_ARTICLES = 2           # 當日少於 2 則不判：單一標題不足以代表「情緒惡化」
ALERT_MIN_BASELINE_DAYS = 10     # 基準窗 20 天中至少 10 天有新聞，否則平均與 σ 不可信
# σ 下限：基準期若幾乎全是中性標題，σ≈0，一則負面就讓 z 爆表。
# 取 0.10 的依據：一則標題分數的變異約 0.2（正負各約一成時），5 則平均的 σ≈0.2；
# 下限取其一半，只擋住退化情形，不改變正常波動股票的判斷。
ALERT_SIGMA_FLOOR = 0.10
# 盤勢報導標題：主體在描述已經發生的股價、大盤或籌碼變化（「台積電跌40元」「三大法人賣超」）。
# LLM 會判成負面，但那只是「已經跌了」的回聲，不是領先價格的新資訊 → 不送評分、不計入分數。
# 清單由使用者 2026-09-14 決定；最後一條是用回測期間外的開發集補上的漏網型態（大盤點數）。
# 已知代價（開發集實測）：真實利空常寫成「X 利空，Y 跌停」，原因與股價在同一則標題裡，會一起被濾掉。
ALERT_PRICE_REPORT_PATTERNS: tuple[str, ...] = (
    r"跌\d+元", r"漲\d+元",
    r"收跌", r"收漲",
    r"跌停", r"漲停",
    r"開盤", r"盤中",
    r"成交量", r"三大法人",
    r"融資", r"融券",
    r"[跌漲挫](逾|近)?[\d,.]+點",
)
# 台股開盤時間（台北，UTC+8，無日光節約）。交易日 s 的分數只用 s 開盤前發布的標題。
ALERT_MARKET_UTC_OFFSET_HOURS = 8
ALERT_MARKET_OPEN_HOUR = 9
ALERT_SCORE_DB_PATH = BACKEND_ROOT / "alert_scores.db"
# 台股中文新聞源：FinMind TaiwanStockNews（免費；註冊 token 讓每小時額度 300→600）
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
# 評分器：production 的 bert-combined 以英文語料訓練，**讀不懂中文標題**，不能直接用在台股新聞。
# 用 LLM 判讀（實驗 #6 的 B2 組、同一份目標導向提示詞）。換評分器＝換版本字串，分數庫依版本分開存。
# 本機 Ollama 模型：回測（tools/alert_backtest.py）與 2026-09-26 以前的線上分數都出自它
ALERT_LLM_MODEL = "gemma3:27b"
ALERT_SCORER_LEGACY = f"llm-{ALERT_LLM_MODEL}"
# 2026-09 起雲端排程沒有 GPU，改用 Google AI Studio 託管的模型（GeminiReviewer；會把標題送到 Google）。
# 與本機版屬於不同評分器：分數另存、不混算；換用後的一致性見 docs/scorer_switch_gemini.md
GEMINI_MODEL = "gemma-3-27b-it"
GEMINI_SYSTEM_INSTRUCTION = True   # 模型不接受 systemInstruction 時改 False（系統提示併入 user turn）
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_RPM = 25                    # 免費層每分鐘上限約 30，留餘裕
ALERT_SCORER = f"llm-gemini:{GEMINI_MODEL}"   # API 讀取的線上評分器
# 預警股票池：鏡像 stock-trend-assistant 的 STOCK_POOL（台灣 50，最後核對 2025-07-01，已知過期）。
# 跨 repo 無法 import 只能複製——以該 repo 為準，變動時兩邊同步。
ALERT_UNIVERSE: dict[str, str] = {
    "1101.TW": "台泥", "1216.TW": "統一", "1301.TW": "台塑", "1303.TW": "南亞", "1326.TW": "台化",
    "2002.TW": "中鋼", "2207.TW": "和泰車", "2301.TW": "光寶科", "2303.TW": "聯電", "2308.TW": "台達電",
    "2317.TW": "鴻海", "2327.TW": "國巨", "2330.TW": "台積電", "2345.TW": "智邦", "2357.TW": "華碩",
    "2379.TW": "瑞昱", "2382.TW": "廣達", "2395.TW": "研華", "2412.TW": "中華電", "2454.TW": "聯發科",
    "2603.TW": "長榮", "2618.TW": "長榮航", "2880.TW": "華南金", "2881.TW": "富邦金", "2882.TW": "國泰金",
    "2883.TW": "凱基金", "2884.TW": "玉山金", "2885.TW": "元大金", "2886.TW": "兆豐金", "2887.TW": "台新金",
    "2890.TW": "永豐金", "2891.TW": "中信金", "2892.TW": "第一金", "2912.TW": "統一超", "3008.TW": "大立光",
    "3017.TW": "奇鋐", "3034.TW": "聯詠", "3037.TW": "欣興", "3045.TW": "台灣大", "3231.TW": "緯創",
    "3661.TW": "世芯-KY", "3711.TW": "日月光投控", "4904.TW": "遠傳", "4938.TW": "和碩", "5871.TW": "中租-KY",
    "5876.TW": "上海商銀", "5880.TW": "合庫金", "6505.TW": "台塑化", "6669.TW": "緯穎",
}

# --- 新聞來源與快取（Phase 5）---
# yfinance：免金鑰、近即時（目前主源）；newsapi：申請表指定源，取得 NEWSAPI_KEY 後切回
NEWS_PROVIDER = "yfinance"
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
NEWS_CACHE_BUCKET_SECONDS = 3600        # 時間桶：同 ticker 一小時內只打一次外部 API
NEWS_DEFAULT_LIMIT = 20

# --- 安全性 ---
# 美股代號格式（含 BRK.B 這類含點者）；ticker 會進快取 key 與外部 query，需驗證防注入
TICKER_PATTERN = r"^[A-Z]{1,5}(\.[A-Z])?$"

# --- CORS（demo 明確 origin，勿用 *）---
# :3000 為本專案前端預設埠；:3001 供與 stock-trend-assistant 前端同時 demo 時使用
# （兩前端預設皆為 :3000，並存時本專案改跑 :3001）。
ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:3001"]
