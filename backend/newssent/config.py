"""唯一設定來源：標籤順序、切分 seed/比例、快取 TTL、情緒指數公式參數等。

不要在 text/、ml/、api/、frontend 各自維護副本——一律從這裡讀取。
標籤順序尤其關鍵：negative/neutral/positive 的索引順序一旦與訓練時錯位，
模型會不報錯地輸出相反情緒；registry 啟動檢查會以此處的順序為準（Phase 4）。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()  # 讀取 backend/.env（若存在）

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

# --- 情緒指數（Phase 5 aggregate.py）---
# score = Σ(sign × confidence) / n，映射 [−1, +1]；|score| 超過門檻才判為正/負，否則中性
SENTIMENT_LABEL_THRESHOLD = 0.15

# --- 新聞來源與快取（Phase 5）---
NEWS_PROVIDER = "newsapi"               # 主源；備援 yfinance 可於此切換
NEWSAPI_KEY = os.environ.get("NEWSAPI_KEY", "")
NEWS_CACHE_BUCKET_SECONDS = 3600        # 時間桶：同 ticker 一小時內只打一次外部 API
NEWS_DEFAULT_LIMIT = 20

# --- 安全性 ---
# 美股代號格式（含 BRK.B 這類含點者）；ticker 會進快取 key 與外部 query，需驗證防注入
TICKER_PATTERN = r"^[A-Z]{1,5}(\.[A-Z])?$"

# --- CORS（demo 明確 origin，勿用 *）---
ALLOWED_ORIGINS = ["http://localhost:3000"]
