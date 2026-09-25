"use client";

/**
 * 跨分頁共用狀態：目前標的、各標的的情緒與新聞、追蹤清單、模型資訊、最近查詢。
 *
 * 掛在 root layout，切換分頁不會重抓——後端限流是每 IP 每分鐘 30 次、所有端點共用，
 * 而經 Next 轉送後所有裝置共用同一個 IP。追蹤清單與模型資訊等到有頁面用到才抓，且只抓一次。
 * setState 只發生在非同步回呼或事件處理中，不在 effect 本體裡直接呼叫。
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import {
  api,
  ApiError,
  TICKER_PATTERN,
  type ModelInfoResponse,
  type NewsResponse,
  type SentimentResponse,
} from "@/lib/api";
import { createLocalStore } from "@/lib/local-store";

export const DEFAULT_TICKER = "AAPL";
export const WATCHLIST = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "AMZN"];
const RECENT_LIMIT = 6;

// 伺服器端回 null：尚未知道使用者上次看哪一檔，不預先用 AAPL 抓一次
const tickerStore = createLocalStore<string | null>(
  "ticker",
  (raw) => (raw && TICKER_PATTERN.test(raw) ? raw : DEFAULT_TICKER),
  null,
);

const recentStore = createLocalStore<string[]>(
  "recent-tickers",
  (raw) => {
    try {
      const parsed: unknown = JSON.parse(raw ?? "[]");
      return Array.isArray(parsed)
        ? parsed.filter((t): t is string => typeof t === "string" && TICKER_PATTERN.test(t)).slice(0, RECENT_LIMIT)
        : [];
    } catch {
      return [];
    }
  },
  [],
);

export interface TickerView {
  sentiment: SentimentResponse | null;
  news: NewsResponse | null;
  error: string | null;
  loading: boolean; // 首次載入或重新整理中；重新整理時保留舊資料
}

export interface WatchRow {
  ticker: string;
  sentiment: SentimentResponse | null; // null＝該檔抓取失敗
}

type Loadable<T> = T | null | "error"; // null＝尚未取得

interface AppState {
  ticker: string | null; // null＝hydration 前，尚未讀到儲存值
  view: TickerView;
  selectTicker: (t: string) => void;
  refresh: () => Promise<boolean> | null; // null＝正在抓，這次不重複送出
  recent: string[];
  watchlist: WatchRow[] | null;
  ensureWatchlist: () => void;
  refreshWatchlist: () => void;
  modelInfo: Loadable<ModelInfoResponse>;
  ensureModelInfo: () => void;
}

const LOADING: TickerView = { sentiment: null, news: null, error: null, loading: true };

export function describeError(e: unknown, ticker: string): string {
  if (!(e instanceof ApiError)) return "發生未知錯誤，請重新整理";
  if (e.status === 404) return `查無 ${ticker} 的近期新聞，換一檔試試`;
  if (e.status === 429) return "查詢太頻繁，請等一分鐘再試";
  if (e.status === 503) return `新聞來源暫時無法使用：${e.message}`;
  return e.message;
}

const AppStateContext = createContext<AppState | null>(null);

export function AppStateProvider({ children }: { children: React.ReactNode }) {
  const ticker = tickerStore.useValue();
  const recent = recentStore.useValue();
  const [views, setViews] = useState<Record<string, TickerView>>({});
  const [watchlist, setWatchlist] = useState<WatchRow[] | null>(null);
  const [modelInfo, setModelInfo] = useState<Loadable<ModelInfoResponse>>(null);

  const requested = useRef(new Set<string>()); // 本次開啟已抓過的標的
  const inflight = useRef(new Set<string>());
  const watchRequested = useRef(false);
  const modelRequested = useRef(false);

  /** 回傳是否成功，給「重新整理」的提示訊息用；錯誤本身已寫進 view.error */
  const fetchTicker = useCallback((t: string): Promise<boolean> => {
    inflight.current.add(t);
    return Promise.all([api.sentiment(t), api.news(t)])
      .then(([sentiment, news]) => {
        setViews((prev) => ({ ...prev, [t]: { sentiment, news, error: null, loading: false } }));
        return true;
      })
      .catch((e: unknown) => {
        setViews((prev) => ({
          ...prev,
          [t]: { sentiment: null, news: null, error: describeError(e, t), loading: false },
        }));
        return false;
      })
      .finally(() => inflight.current.delete(t));
  }, []);

  useEffect(() => {
    if (ticker && !requested.current.has(ticker)) {
      requested.current.add(ticker);
      fetchTicker(ticker);
    }
  }, [ticker, fetchTicker]);

  const selectTicker = useCallback((t: string) => {
    tickerStore.set(t);
    const next = [t, ...recentStore.get().filter((x) => x !== t)].slice(0, RECENT_LIMIT);
    recentStore.set(JSON.stringify(next));
  }, []);

  const refresh = useCallback((): Promise<boolean> | null => {
    if (!ticker || inflight.current.has(ticker)) return null;
    setViews((prev) => ({ ...prev, [ticker]: { ...(prev[ticker] ?? LOADING), loading: true } }));
    return fetchTicker(ticker);
  }, [ticker, fetchTicker]);

  const loadWatchlist = useCallback(() => {
    Promise.all(
      WATCHLIST.map((t) =>
        api
          .sentiment(t)
          .then((sentiment): WatchRow => ({ ticker: t, sentiment }))
          .catch((): WatchRow => ({ ticker: t, sentiment: null })),
      ),
    ).then(setWatchlist);
  }, []);

  const ensureWatchlist = useCallback(() => {
    if (watchRequested.current) return;
    watchRequested.current = true;
    loadWatchlist();
  }, [loadWatchlist]);

  const refreshWatchlist = useCallback(() => {
    watchRequested.current = true;
    setWatchlist(null);
    loadWatchlist();
  }, [loadWatchlist]);

  const ensureModelInfo = useCallback(() => {
    if (modelRequested.current) return;
    modelRequested.current = true;
    api
      .modelInfo()
      .then(setModelInfo)
      .catch(() => setModelInfo("error"));
  }, []);

  const value = useMemo<AppState>(
    () => ({
      ticker,
      view: (ticker && views[ticker]) || LOADING,
      selectTicker,
      refresh,
      recent,
      watchlist,
      ensureWatchlist,
      refreshWatchlist,
      modelInfo,
      ensureModelInfo,
    }),
    [ticker, views, selectTicker, refresh, recent, watchlist, ensureWatchlist, refreshWatchlist, modelInfo, ensureModelInfo],
  );

  return <AppStateContext.Provider value={value}>{children}</AppStateContext.Provider>;
}

export function useAppState(): AppState {
  const ctx = useContext(AppStateContext);
  if (!ctx) throw new Error("useAppState 必須在 AppStateProvider 內使用");
  return ctx;
}
