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
}


def company_name(ticker: str) -> str:
    return TICKER_COMPANY_NAMES.get((ticker or "").upper(), ticker)


# --- 情緒指數（Phase 5 aggregate.py）---
# score = Σ(sign × confidence) / n，映射 [−1, +1]；|score| 超過門檻才判為正/負，否則中性
SENTIMENT_LABEL_THRESHOLD = 0.15

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
