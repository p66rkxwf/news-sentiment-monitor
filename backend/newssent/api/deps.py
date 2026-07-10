"""ticker 格式驗證 —— /sentiment、/news 各 endpoint 共用同一處檢查。

美股代號開放（不像台股有固定股票池），因此只驗格式、不驗白名單；
格式驗證的主要目的是防注入與路徑穿越（ticker 會進快取 key 與外部 API query）。
"""

from fastapi import Path

from newssent.api.errors import InvalidTickerFormatError
from newssent.data.cache import InvalidTickerError, validate_ticker


def get_valid_ticker(ticker: str = Path(...)) -> str:
    try:
        return validate_ticker(ticker.upper())
    except InvalidTickerError:
        raise InvalidTickerFormatError(ticker)
