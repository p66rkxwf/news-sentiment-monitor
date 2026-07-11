"use client";

/**
 * 主監控儀表板：代號搜尋 → 情緒指針 ＋ 關鍵字雲 ＋ 新聞列表。
 * 顯示 as_of 時間戳與 stale 徽章（快取降級時使用者要知道資料非最新）＋投資免責聲明。
 * 錯誤處理對應 Phase 0 凍結契約（422/404/503）。
 */

import { useCallback, useEffect, useState } from "react";
import KeywordCloud from "@/components/KeywordCloud";
import NewsList from "@/components/NewsList";
import SentimentGauge from "@/components/SentimentGauge";
import TickerSearch from "@/components/TickerSearch";
import {
  api,
  ApiError,
  type ModelInfoResponse,
  type NewsResponse,
  type SentimentResponse,
} from "@/lib/api";

export default function Home() {
  const [ticker, setTicker] = useState("AAPL");
  const [sentiment, setSentiment] = useState<SentimentResponse | null>(null);
  const [news, setNews] = useState<NewsResponse | null>(null);
  const [modelInfo, setModelInfo] = useState<ModelInfoResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.modelInfo().then(setModelInfo).catch(() => setModelInfo(null));
  }, []);

  const load = useCallback(async (t: string) => {
    setLoading(true);
    setError(null);
    try {
      const [s, n] = await Promise.all([api.sentiment(t), api.news(t)]);
      setSentiment(s);
      setNews(n);
    } catch (e) {
      setSentiment(null);
      setNews(null);
      if (e instanceof ApiError) {
        setError(
          e.status === 503
            ? `新聞來源暫時無法使用：${e.message}`
            : e.status === 404
              ? `查無 ${t} 的近期新聞`
              : e.message,
        );
      } else {
        setError("發生未知錯誤");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load(ticker);
  }, [ticker, load]);

  const stale = sentiment?.stale || news?.stale;
  const isMock = sentiment?.is_mock || news?.is_mock;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">財經新聞情緒監控</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
            NLP 情緒分析 × 即時新聞 × 美股標的
          </p>
        </div>
        <TickerSearch selected={ticker} onSelect={setTicker} />
      </header>

      {(stale || isMock) && (
        <div className="mb-4 flex flex-wrap gap-2">
          {stale && (
            <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-300">
              ⚠ 新聞來源暫時失效，顯示的是快取的舊資料（stale）
            </span>
          )}
          {isMock && (
            <span className="rounded-full bg-purple-100 px-3 py-1 text-xs font-medium text-purple-800 dark:bg-purple-900/40 dark:text-purple-300">
              ⚠ 模型尚未載入，目前為示意資料
            </span>
          )}
        </div>
      )}

      {error && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-800 dark:bg-red-900/30 dark:text-red-300">
          {error}
        </div>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
          <h2 className="mb-3 text-sm font-medium text-gray-500 dark:text-gray-400">
            {ticker} 整體情緒指數
          </h2>
          {loading && (
            <div className="flex h-48 items-center justify-center text-sm text-gray-400">
              分析中…
            </div>
          )}
          {!loading && sentiment && (
            <>
              <SentimentGauge score={sentiment.score} label={sentiment.label} />
              <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 border-t border-gray-100 pt-3 text-xs text-gray-500 dark:border-gray-800 dark:text-gray-400">
                <dt>分析新聞數</dt>
                <dd className="text-right">{sentiment.article_count} 則</dd>
                <dt>模型版本</dt>
                <dd className="text-right">{sentiment.model_version}</dd>
                {modelInfo?.test_macro_f1 != null && (
                  <>
                    <dt>測試集 Macro F1</dt>
                    <dd className="text-right">{modelInfo.test_macro_f1.toFixed(4)}</dd>
                  </>
                )}
                <dt>資料時間（as_of）</dt>
                <dd className="text-right">{sentiment.as_of.slice(0, 16).replace("T", " ")} UTC</dd>
              </dl>
            </>
          )}
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
          <h2 className="mb-3 text-sm font-medium text-gray-500 dark:text-gray-400">
            熱門討論關鍵字
          </h2>
          {loading && (
            <div className="flex h-48 items-center justify-center text-sm text-gray-400">
              載入中…
            </div>
          )}
          {!loading && sentiment && <KeywordCloud keywords={sentiment.keywords} />}
        </section>
      </div>

      <section className="mt-6 rounded-xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-900">
        <h2 className="mb-2 text-sm font-medium text-gray-500 dark:text-gray-400">
          近期新聞（每則附情緒標籤與信心分數）
        </h2>
        {loading && <p className="py-6 text-center text-sm text-gray-400">載入中…</p>}
        {!loading && news && <NewsList articles={news.articles} />}
      </section>

      <footer className="mt-8 space-y-1 text-center text-xs text-gray-400 dark:text-gray-600">
        <p>
          免責聲明：情緒指數為機器學習模型之統計輸出，僅供學術研究與參考，不構成任何投資建議。
        </p>
        <p>彰師大 115 年百萬專題探索 — 基於自然語言處理之新聞情緒分析與即時監控系統</p>
      </footer>
    </main>
  );
}
