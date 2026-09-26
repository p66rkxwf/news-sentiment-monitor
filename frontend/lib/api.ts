/**
 * 後端 API client — 型別對應 backend/newssent/api/schemas.py（Phase 0 凍結契約）。
 * 錯誤格式統一為 {"error": {"code", "message"}}；以 code 判斷錯誤類型，勿比對 message。
 * 預設走同源 /api/*，由 next.config.ts 轉送到 FastAPI（:8001）；設 NEXT_PUBLIC_API_BASE 可改回直連。
 *
 * 靜態站模式（NEXT_PUBLIC_STATIC_DATA=1，news.sekinv.com）：沒有後端，改讀每日排程匯出的
 * /data/*.json（backend/newssent/export_static.py），只提供 NEXT_PUBLIC_TICKERS 列出的標的。
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
export const STATIC_DATA = process.env.NEXT_PUBLIC_STATIC_DATA === "1";
const DATA_BASE = "/data";

/** 靜態站每日預先計算的標的（build 時由 config.STATIC_TICKERS 帶入）；即時後端模式為空＝不限 */
export const CURATED_TICKERS: string[] = (process.env.NEXT_PUBLIC_TICKERS ?? "")
  .split(",")
  .map((t) => t.trim())
  .filter(Boolean);

export type SentimentLabel = "negative" | "neutral" | "positive";

export interface KeywordScore {
  word: string;
  score: number;
}

export interface SentimentResponse {
  ticker: string;
  score: number; // [-1, +1]
  label: SentimentLabel;
  article_count: number;
  keywords: KeywordScore[];
  model_version: string;
  as_of: string;
  stale: boolean;
  is_mock: boolean;
}

export interface NewsItem {
  title: string;
  url: string;
  published_at: string;
  sentiment: SentimentLabel;
  confidence: number;
}

export interface NewsResponse {
  ticker: string;
  articles: NewsItem[];
  stale: boolean;
  is_mock: boolean;
}

export interface ModelInfoResponse {
  model_version: string;
  trained_at: string | null;
  test_macro_f1: number | null;
  is_mock: boolean;
}

// --- 台股情緒異常預警（GET /api/alerts）---

export type AlertLevel = "high" | "watch" | "normal" | "insufficient";

export interface DailySentimentPoint {
  session: string;
  score: number | null; // null＝當日無標題
  article_count: number;
}

export interface AlertEvidence {
  title: string;
  source: string;
  published_at: string; // ISO8601 UTC
  score: number;
}

export interface StockAlert {
  ticker: string;
  name: string;
  level: AlertLevel;
  reason: string | null; // insufficient 時說明缺什麼
  z_score: number | null;
  score_today: number | null;
  baseline_mean: number | null;
  baseline_std: number | null;
  score_change: number | null;
  article_count: number;
  baseline_days: number;
  recent_score: number | null;
  recent: DailySentimentPoint[];
  evidence: AlertEvidence[];
}

export interface AlertSummary {
  high: number;
  watch: number;
  normal: number;
  insufficient: number;
}

export interface AlertsResponse {
  as_of: string;
  window_closed: boolean;
  scorer: string;
  params: Record<string, number>;
  universe_size: number;
  summary: AlertSummary;
  alerts: StockAlert[];
}

export interface AlertSessionsResponse {
  sessions: string[];
  latest: string;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

const BACKEND_DOWN = STATIC_DATA
  ? "資料暫時無法取得，請稍後再試"
  : "無法連線到後端服務，請確認 API 已在 :8001 啟動";

async function request<T>(path: string, base: string = API_BASE): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${base}${path}`);
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", BACKEND_DOWN);
  }
  if (!res.ok) {
    if (STATIC_DATA && res.status === 404) {
      throw new ApiError(404, "NOT_FOUND", "此項資料今日未產生（每日排程匯出時失敗）");
    }
    const body = await res.json().catch(() => null);
    const err = body?.error;
    // 轉送目標沒開時，Next 回的是非 JSON 的 5xx，沒有後端錯誤格式可讀
    if (!err && res.status >= 500) throw new ApiError(res.status, "BACKEND_UNREACHABLE", BACKEND_DOWN);
    throw new ApiError(res.status, err?.code ?? "UNKNOWN", err?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

const liveApi = {
  sentiment: (ticker: string) =>
    request<SentimentResponse>(`/api/stocks/${encodeURIComponent(ticker)}/sentiment`),
  news: (ticker: string) =>
    request<NewsResponse>(`/api/stocks/${encodeURIComponent(ticker)}/news`),
  modelInfo: () => request<ModelInfoResponse>("/api/model"),
  alerts: (asOf?: string, includeAll = false) => {
    const q = new URLSearchParams();
    if (asOf) q.set("as_of", asOf);
    if (includeAll) q.set("include_all", "true");
    const qs = q.toString();
    return request<AlertsResponse>(`/api/alerts${qs ? `?${qs}` : ""}`);
  },
  alertSessions: () => request<AlertSessionsResponse>("/api/alerts/sessions"),
};

/** 美股代號格式（與後端 deps.py 一致）；提交前先擋掉明顯錯誤格式 */
export const TICKER_PATTERN = /^[A-Z]{1,5}(\.[A-Z])?$/;

/** 格式正確，且（靜態站時）在每日預先計算的清單內 */
export function isAllowedTicker(t: string): boolean {
  return TICKER_PATTERN.test(t) && (CURATED_TICKERS.length === 0 || CURATED_TICKERS.includes(t));
}

// --- 靜態站 ---

/** 匯出摘要（export_static.py 的 meta.json） */
export interface SiteMeta {
  generated_at: string; // ISO UTC
  model_version: string;
  scorer: string;
  alerts_latest: string | null;
  alerts_status: "ok" | "quota" | "failed" | null; // 當日台股新聞評分結果
}

type ExportedBoard = AlertsResponse & { opens_at: string };
type ExportedCalendar = { sessions: string[]; latest: string | null };

const TRIGGERED: AlertLevel[] = ["high", "watch"];
const staticGet = <T>(path: string) => request<T>(path, DATA_BASE);
const enc = encodeURIComponent;

let metaPromise: Promise<SiteMeta> | null = null;
export function siteMeta(): Promise<SiteMeta> {
  metaPromise ??= staticGet<SiteMeta>("/meta.json").catch((e) => {
    metaPromise = null; // 失敗不快取，下次重試
    throw e;
  });
  return metaPromise;
}

async function staticCalendar(): Promise<AlertSessionsResponse> {
  const cal = await staticGet<ExportedCalendar>("/alerts/sessions.json");
  if (!cal.latest || cal.sessions.length === 0) {
    // 換用新評分器後，基準期（20 個交易日）還沒累積滿之前沒有可判斷的看板
    throw new ApiError(503, "ALERT_DATA_UNAVAILABLE", "預警資料準備中：評分基準期尚未累積滿");
  }
  return { sessions: cal.sessions, latest: cal.latest };
}

const staticApi: typeof liveApi = {
  sentiment: (ticker) => staticGet(`/stocks/${enc(ticker)}/sentiment.json`),
  news: (ticker) => staticGet(`/stocks/${enc(ticker)}/news.json`),
  modelInfo: () => staticGet("/model.json"),
  alertSessions: staticCalendar,
  alerts: async (asOf, includeAll = false) => {
    const day = asOf ?? (await staticCalendar()).latest;
    let board: ExportedBoard;
    try {
      board = await staticGet<ExportedBoard>(`/alerts/${enc(day)}.json`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        throw new ApiError(422, "INVALID_SESSION", `${day} 沒有可顯示的預警看板（非交易日或超出保留範圍）`);
      }
      throw e;
    }
    // 匯出檔含全池（include_all）；預設只列 high / watch，順序與 summary 同後端
    const { opens_at, ...rest } = board;
    return {
      ...rest,
      window_closed: Date.now() >= Date.parse(opens_at), // 匯出當下凍結的值，依現在時間重算
      alerts: includeAll ? board.alerts : board.alerts.filter((a) => TRIGGERED.includes(a.level)),
    };
  },
};

export const api = STATIC_DATA ? staticApi : liveApi;
