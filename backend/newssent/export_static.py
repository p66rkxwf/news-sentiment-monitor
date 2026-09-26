"""靜態站匯出：python -m newssent.export_static --out ../frontend/public/data

公開站 news.sekinv.com 沒有常駐後端：每日排程跑完 alert_recorder 之後，以 TestClient 逐一呼叫
現有 API，把回應原樣寫成 JSON，前端 staticApi（frontend/lib/api.ts）改讀這些檔案。
走 API 本身的程式路徑＝靜態站與本機 uvicorn 的數字同源，不另寫一套計算。

- 個股新聞與情緒：config.STATIC_TICKERS 每檔各一份（/sentiment 與 /news 共用一小時快取桶，
  第二次呼叫不再打 Yahoo；Yahoo 失敗時 API 退回 news_cache.db 的舊資料並標 stale）
- 情緒預警：最近 ALERT_EXPORT_SESSIONS 個交易日的全池看板（include_all=true，前端自行過濾
  high/watch）。整個看板都是「資料不足」的交易日不匯出——換用新評分器後、基準期還沒累積滿
  的那段日子沒有任何可判斷的內容。每份看板另附 opens_at：window_closed 在匯出當下就凍結了，
  前端依 opens_at 與現在時間重算

關卡（任一不過 → exit 1；workflow 不部署，線上維持上一版）：
- 模型必須真的載入（is_mock=false）：找不到 artifact 時 API 會退回 mock，不能把假情緒發布出去
- 個股檔案覆蓋率 ≥ MIN_TICKER_COVERAGE
- 預警最新交易日不得早於上一版（--prev；分數庫還原失敗的徵兆）
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections.abc import Iterable
from datetime import date, datetime, timezone
from pathlib import Path

ALERT_EXPORT_SESSIONS = 120
MIN_TICKER_COVERAGE = 0.7


class ExportError(Exception):
    """關卡未通過：不得部署。"""


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _run_url() -> str | None:
    server, repo, run = (os.environ.get(k) for k in ("GITHUB_SERVER_URL", "GITHUB_REPOSITORY", "GITHUB_RUN_ID"))
    return f"{server}/{repo}/actions/runs/{run}" if server and repo and run else None


def run_export(
    client,
    out: Path,
    *,
    tickers: Iterable[str],
    session_limit: int = ALERT_EXPORT_SESSIONS,
    prev_meta: dict | None = None,
    alerts_status: str | None = None,
    log=print,
) -> dict:
    """逐一呼叫 API 寫出 JSON；回傳 meta。關卡不過拋 ExportError。"""
    from newssent.config import ALERT_SCORER, company_name
    from newssent.inference.alerts import session_open

    failures: list[str] = []
    written = 0

    def get(url: str, required: bool = False) -> dict | None:
        resp = client.get(url)
        if resp.status_code != 200:
            msg = f"{url} → HTTP {resp.status_code}: {resp.text[:200]}"
            if required:
                raise ExportError(msg)
            failures.append(msg)
            log(f"[略過] {msg}")
            return None
        return resp.json()

    def write(relpath: str, payload: dict) -> None:
        nonlocal written
        _write_json(out / relpath, payload)
        written += 1

    model = get("/api/model", required=True)
    if model.get("is_mock"):
        raise ExportError("/api/model 為 mock 回應（模型未載入）——拒絕發布假資料")
    write("model.json", model)

    t0 = time.monotonic()
    tickers = list(tickers)
    ok = 0
    for t in tickers:
        for endpoint in ("sentiment", "news"):
            body = get(f"/api/stocks/{t}/{endpoint}")
            if body is not None:
                write(f"stocks/{t}/{endpoint}.json", body)
                ok += 1
    coverage = ok / (2 * len(tickers)) if tickers else 1.0
    log(f"個股 {len(tickers)} 檔：覆蓋率 {coverage:.0%}（{time.monotonic() - t0:.0f}s）")
    if coverage < MIN_TICKER_COVERAGE:
        raise ExportError(f"個股檔案覆蓋率 {coverage:.0%} < {MIN_TICKER_COVERAGE:.0%}：\n  " + "\n  ".join(failures[:20]))
    write("tickers.json", {"tickers": tickers, "names": {t: company_name(t) for t in tickers}})

    # 分數庫沒有任何交易日時 API 回 503：此時沒有預警可發布，但新聞與情緒照常部署
    calendar = get("/api/alerts/sessions")
    exported: list[str] = []
    for s in (calendar or {}).get("sessions", [])[-session_limit:]:
        board = get(f"/api/alerts?as_of={s}&include_all=true")
        if board is None or board["summary"]["insufficient"] == board["universe_size"]:
            continue
        board["opens_at"] = session_open(date.fromisoformat(s)).isoformat()
        write(f"alerts/{s}.json", board)
        exported.append(s)
    latest = exported[-1] if exported else None
    write("alerts/sessions.json", {"sessions": exported, "latest": latest})
    log(f"預警看板 {len(exported)} 個交易日（最新 {latest}，{time.monotonic() - t0:.0f}s）")

    prev_latest = (prev_meta or {}).get("alerts_latest")
    if prev_latest and (latest is None or latest < prev_latest):
        raise ExportError(f"預警最新交易日倒退：本次 {latest}、上一版 {prev_latest}（分數庫還原失敗？）")

    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model_version": model["model_version"],
        "scorer": ALERT_SCORER,
        "alerts_latest": latest,
        # 當日 alert_recorder 的結果（ok / quota / failed）：評分額度用盡時看板可能只更新一部分
        "alerts_status": alerts_status,
        "tickers": tickers,
        "coverage": round(coverage, 4),
        "failures": failures,
        "commit": os.environ.get("GITHUB_SHA"),
        "run_url": _run_url(),
    }
    write("meta.json", meta)
    log(f"完成：{written} 檔")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="匯出靜態站 JSON")
    parser.add_argument("--out", type=Path, required=True, help="輸出目錄（frontend/public/data）")
    parser.add_argument("--prev", type=Path, help="上一版 meta.json；預警日期倒退則拒絕")
    parser.add_argument("--sessions", type=int, default=ALERT_EXPORT_SESSIONS, help="預警看板匯出交易日數")
    parser.add_argument("--alerts-status", choices=("ok", "quota", "failed"), help="當日 alert_recorder 結果")
    parser.add_argument("--tickers", nargs="+", help="只匯出指定標的（除錯用）")
    args = parser.parse_args(argv)

    from fastapi.testclient import TestClient

    from newssent.api import main as api_main
    from newssent.config import STATIC_TICKERS

    prev_meta = None
    if args.prev and args.prev.exists():
        prev_meta = json.loads(args.prev.read_text(encoding="utf-8"))

    try:
        with TestClient(api_main.app) as client:
            api_main.app.state.limiter.enabled = False  # 同一個 "testclient" IP 連打上百次，會誤觸每分鐘限流
            run_export(
                client,
                args.out,
                tickers=args.tickers or STATIC_TICKERS,
                session_limit=args.sessions,
                prev_meta=prev_meta,
                alerts_status=args.alerts_status,
            )
    except ExportError as exc:
        print(f"[匯出失敗] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
