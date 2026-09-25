# frontend

財經新聞情緒監控的前端：Next.js 16 分頁式 App，可加到手機主畫面（PWA）。
整體說明、後端啟動與手機 demo 步驟見專案根目錄的 [README](../README.md)，架構見 [docs/architecture.md](../docs/architecture.md)。

```powershell
npm install
npm run dev          # http://localhost:3000（開發）
npm run build; npm start   # 正式模式；手機用區網 IP 開 3000
npm run lint
```

| 環境變數 | 用途 |
|---|---|
| `API_PROXY_TARGET` | `/api/*` 轉送目標，預設 `http://127.0.0.1:8001` |
| `DEV_ORIGINS` | dev 模式允許的區網來源（逗號分隔，例如 `192.168.1.23`） |
| `NEXT_PUBLIC_API_BASE` | 設了就改成瀏覽器直連後端（需自行處理後端 CORS），一般不用設 |

目錄：`app/` 五個分頁與 manifest、圖示；`components/` 介面元件；`lib/` API client、共用狀態、主題與格式化。
這個 Next 版本有破壞性變更，改程式前先讀 `node_modules/next/dist/docs/`（見 [AGENTS.md](AGENTS.md)）。
