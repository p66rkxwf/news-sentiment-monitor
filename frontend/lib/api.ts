/**
 * 後端 API client — 型別對應 backend/newssent/api/schemas.py（Phase 0 凍結契約）。
 * 錯誤格式統一為 {"error": {"code", "message"}}；以 code 判斷錯誤類型，勿比對 message。
 * news 後端預設跑在 :8001（stock 專案佔 :8000）。
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001";

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

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(path: string): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`);
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "無法連線到後端服務，請確認 API 已啟動");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const err = body?.error;
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
};

/** 美股代號格式（與後端 deps.py 一致）；提交前先擋掉明顯錯誤格式 */
export const TICKER_PATTERN = /^[A-Z]{1,5}(\.[A-Z])?$/;
