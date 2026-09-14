"""統一錯誤回應格式：{"error": {"code": ..., "message": ...}}。

422 = 代號格式錯誤／非交易日、404 = 查無新聞、503 = 新聞源失敗且無快取可退／尚無預警資料。
這是 Phase 0 凍結的契約，前後端都依 code 判斷錯誤類型，不要用字串比對 message。
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message


class InvalidTickerFormatError(ApiError):
    def __init__(self, ticker: str):
        super().__init__(422, "INVALID_TICKER_FORMAT", f"股票代號格式錯誤: {ticker}")


class NewsNotFoundError(ApiError):
    def __init__(self, ticker: str):
        super().__init__(404, "NEWS_NOT_FOUND", f"查無 {ticker} 的相關新聞")


class NewsSourceUnavailableError(ApiError):
    def __init__(self, detail: str):
        super().__init__(503, "NEWS_SOURCE_UNAVAILABLE", detail)


class InvalidSessionError(ApiError):
    def __init__(self, as_of: str):
        super().__init__(422, "INVALID_SESSION", f"{as_of} 不在交易日曆中（非交易日或超出資料範圍）")


class AlertDataUnavailableError(ApiError):
    def __init__(self):
        super().__init__(
            503,
            "ALERT_DATA_UNAVAILABLE",
            "尚無預警資料，請先執行 python -m newssent.inference.alert_recorder",
        )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )
