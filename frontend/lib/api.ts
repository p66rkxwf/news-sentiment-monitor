/**
 * 後端 API client — 型別對應 backend/newssent/api/schemas.py（Phase 0 凍結契約）。
 * 錯誤格式統一為 {"error": {"code", "message"}}；以 code 判斷錯誤類型，勿比對 message。
 * 預設走同源 /api/*，由 next.config.ts 轉送到 FastAPI（:8001）；設 NEXT_PUBLIC_API_BASE 可改回直連。
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";

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

const BACKEND_DOWN = "無法連線到後端服務，請確認 API 已在 :8001 啟動";

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`);
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", BACKEND_DOWN);
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const err = body?.error;
    // 轉送目標沒開時，Next 回的是非 JSON 的 5xx，沒有後端錯誤格式可讀
    if (!err && res.status >= 500) throw new ApiError(res.status, "BACKEND_UNREACHABLE", BACKEND_DOWN);
    throw new ApiError(res.status, err?.code ?? "UNKNOWN", err?.message ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
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
