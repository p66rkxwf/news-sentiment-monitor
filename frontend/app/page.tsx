"use client";

/**
 * 主監控儀表板：代號搜尋 → 情緒指針 ＋ 情緒分佈 ＋ 追蹤清單比較 ＋ 關鍵字雲 ＋ 新聞列表。
 * as_of 時間戳與 stale/mock 徽章、投資免責聲明。錯誤處理對應 Phase 0 凍結契約（422/404/503）。
 */

import { useCallback, useEffect, useState } from "react";
import KeywordCloud from "@/components/KeywordCloud";
import NewsList from "@/components/NewsList";
import SentimentDistribution from "@/components/SentimentDistribution";
import SentimentGauge from "@/components/SentimentGauge";
import ThemeToggle from "@/components/ThemeToggle";
import TickerSearch from "@/components/TickerSearch";
import WatchlistCompare from "@/components/WatchlistCompare";
import {
  api,
  ApiError,
  type ModelInfoResponse,
  type NewsResponse,
  type SentimentResponse,
} from "@/lib/api";

function Card({
  title,
  children,
  className = "",
  action,
}: {
  title?: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <section
      className={`rounded-2xl border border-border bg-surface p-5 shadow-(--shadow-sm) ${className}`}
    >
      {title && (
        <div className="mb-3 flex items-center justify-between gap-2">
          <h2 className="text-sm font-semibold text-ink-2">{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** 分組標題帶：與 stock 儀表板共用同一設計語言。左 accent 短條＋右細分隔線。 */
function SectionHeading({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={`mb-4 flex items-center gap-3 ${className}`}>
      <span className="h-4 w-1 rounded-full bg-accent" />
      <h2 className="text-sm font-semibold tracking-tight text-ink">{children}</h2>
      <span className="h-px flex-1 bg-border" />
    </div>
  );
}

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
    <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-accent-fg shadow-(--shadow-md)">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M3 3v18h18" />
              <path d="M7 14l3-3 3 3 4-5" />
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight sm:text-2xl">財經新聞情緒監控</h1>
            <p className="mt-0.5 text-sm text-ink-3">NLP 情緒分析 · 即時新聞 · 美股標的</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <TickerSearch selected={ticker} onSelect={setTicker} />
          <ThemeToggle />
        </div>
      </header>

      {(stale || isMock) && (
        <div className="mb-4 flex flex-wrap gap-2">
          {stale && (
            <span className="rounded-full px-3 py-1 text-xs font-medium" style={{ background: "var(--neu-soft)", color: "var(--ink-2)" }}>
              ⚠ 新聞來源暫時失效，顯示快取的舊資料（stale）
            </span>
          )}
          {isMock && (
            <span className="rounded-full px-3 py-1 text-xs font-medium" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>
              ⚠ 模型尚未載入，目前為示意資料
            </span>
          )}
        </div>
      )}

      {error && (
        <div
          className="mb-6 rounded-xl border px-4 py-3 text-sm"
          style={{ borderColor: "var(--neg)", background: "var(--neg-soft)", color: "var(--neg)" }}
        >
          {error}
        </div>
      )}

      <SectionHeading>情緒總覽</SectionHeading>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* 主情緒卡 */}
        <Card
          title={`${ticker} 整體情緒指數`}
          className="animate-fadeup lg:col-span-2"
          action={
            sentiment && (
              <span className="text-[11px] text-ink-3">
                {sentiment.article_count} 則 · {sentiment.as_of.slice(0, 10)}
              </span>
            )
          }
        >
          {loading ? (
            <div className="flex h-56 items-center justify-center text-sm text-ink-3">分析中…</div>
          ) : sentiment && news ? (
            <div className="grid gap-6 sm:grid-cols-2 sm:items-center">
              <SentimentGauge score={sentiment.score} label={sentiment.label} />
              <div>
                <p className="mb-2 text-xs font-medium text-ink-3">近期新聞情緒分佈</p>
                <SentimentDistribution articles={news.articles} />
              </div>
            </div>
          ) : (
            <div className="flex h-56 items-center justify-center text-sm text-ink-3">無資料</div>
          )}
        </Card>

        {/* 追蹤清單比較（新功能） */}
        <Card title="追蹤清單情緒比較" className="animate-fadeup">
          <WatchlistCompare selected={ticker} onSelect={setTicker} />
        </Card>
      </div>

      <SectionHeading className="mt-8">新聞明細</SectionHeading>

      <div className="grid gap-5 lg:grid-cols-3">
        <Card title="熱門討論關鍵字" className="animate-fadeup lg:col-span-1">
          {loading ? (
            <div className="flex h-32 items-center justify-center text-sm text-ink-3">載入中…</div>
          ) : sentiment ? (
            <KeywordCloud keywords={sentiment.keywords} ticker={ticker} />
          ) : null}
        </Card>

        <Card title="近期新聞（附情緒標籤與信心分數）" className="animate-fadeup lg:col-span-2">
          {loading ? (
            <p className="py-6 text-center text-sm text-ink-3">載入中…</p>
          ) : news ? (
            <NewsList articles={news.articles} />
          ) : null}
        </Card>
      </div>

      {modelInfo && !modelInfo.is_mock && (
        <div className="mt-5 flex flex-wrap items-center justify-center gap-x-6 gap-y-1 rounded-xl border border-border bg-surface-2 px-4 py-2.5 text-[11px] text-ink-3">
          <span>模型 {modelInfo.model_version}</span>
          {modelInfo.test_macro_f1 != null && <span>測試集 Macro F1 {modelInfo.test_macro_f1.toFixed(4)}</span>}
          {modelInfo.trained_at && <span>訓練於 {modelInfo.trained_at.slice(0, 10)}</span>}
        </div>
      )}

      <footer className="mt-8 space-y-1 text-center text-xs text-ink-3">
        <p>免責聲明：情緒指數為機器學習模型之統計輸出，僅供學術研究與參考，不構成任何投資建議。</p>
        <p>彰師大 115 年百萬專題探索 — 基於自然語言處理之新聞情緒分析與即時監控系統</p>
      </footer>
    </main>
  );
}
