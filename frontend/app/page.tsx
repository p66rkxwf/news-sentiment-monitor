"use client";

/**
 * 總覽：目前標的的情緒指數（新聞刻度帶）、情緒分佈、熱門關鍵字、最新幾則新聞。
 * 每個區塊在載入中都有同樣高度的骨架，資料到了不會把下方內容往下推（避免版面跳動）。
 * 錯誤處理對應 Phase 0 凍結契約（422/404/503），訊息對照在 app-state.describeError。
 */

import { ChevronRight, Hash, PieChart, SearchX } from "lucide-react";
import Link from "next/link";
import KeywordList from "@/components/KeywordList";
import NewsList from "@/components/NewsList";
import Panel from "@/components/Panel";
import SentimentDistribution from "@/components/SentimentDistribution";
import SentimentScale from "@/components/SentimentScale";
import Skeleton from "@/components/Skeleton";
import StatusBanner from "@/components/StatusBanner";
import { TickerBar } from "@/components/TopBar";
import { useAppState } from "@/lib/app-state";

const PREVIEW = 5;

function HeroSkeleton() {
  return (
    <div className="card space-y-5 p-5 sm:p-6">
      <div className="flex justify-between">
        <Skeleton className="h-7 w-24 rounded-full" />
        <Skeleton className="h-5 w-28" />
      </div>
      <Skeleton className="h-4 w-16" />
      <Skeleton className="h-12 w-40" />
      <Skeleton className="h-20 w-full" />
      <Skeleton className="h-8 w-full" />
    </div>
  );
}

export default function OverviewPage() {
  const { ticker, view, refresh } = useAppState();
  const { sentiment, news, error } = view;
  const ready = sentiment && news;
  const firstLoad = !ready && !error;

  return (
    <>
      <TickerBar width="wide" />
      <StatusBanner
        width="wide"
        error={error}
        stale={sentiment?.stale || news?.stale}
        mock={sentiment?.is_mock || news?.is_mock}
        onRetry={refresh}
      />

      <main className="mx-auto grid w-full max-w-6xl gap-4 px-4 pt-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:items-start lg:gap-6 lg:px-8 lg:pt-6">
        <div className="space-y-4 lg:space-y-6">
          {ready ? (
            <SentimentScale
              score={sentiment.score}
              label={sentiment.label}
              articles={news.articles}
              articleCount={sentiment.article_count}
              asOf={sentiment.as_of}
            />
          ) : firstLoad ? (
            <HeroSkeleton />
          ) : (
            <div className="card flex flex-col items-center gap-3 px-6 py-12 text-center">
              <span className="flex size-12 items-center justify-center rounded-full bg-surface-2 text-ink-3">
                <SearchX size={22} />
              </span>
              <p className="text-body text-ink-2">點上方的代號換一檔，或稍後按「重試」。</p>
            </div>
          )}

          {(ready || firstLoad) && (
            <>
              <Panel title="新聞情緒分佈" icon={PieChart}>
                {ready ? <SentimentDistribution articles={news.articles} /> : <Skeleton className="h-30 w-full" />}
              </Panel>
              <Panel title="熱門關鍵字" icon={Hash}>
                {ready ? (
                  <KeywordList keywords={sentiment.keywords} ticker={ticker ?? undefined} />
                ) : (
                  <div className="space-y-3">
                    {Array.from({ length: 6 }, (_, i) => (
                      <Skeleton key={i} className="h-6 w-full" />
                    ))}
                  </div>
                )}
              </Panel>
            </>
          )}
        </div>

        {(ready || firstLoad) && (
          <section className="lg:sticky lg:top-[calc(env(safe-area-inset-top)+5.5rem)]">
            <div className="mb-3 flex min-h-11 items-center justify-between px-1">
              <h2 className="text-body font-semibold text-ink-2">最新新聞</h2>
              {ready && news.articles.length > PREVIEW && (
                <Link href="/news" className="flex min-h-11 items-center gap-0.5 text-body text-brand">
                  看全部 {news.articles.length} 則
                  <ChevronRight size={16} />
                </Link>
              )}
            </div>
            {ready ? (
              <NewsList articles={news.articles} limit={PREVIEW} />
            ) : (
              <div className="card divide-y divide-hairline">
                {Array.from({ length: PREVIEW }, (_, i) => (
                  <div key={i} className="space-y-2.5 px-4 py-3.5">
                    <Skeleton className="h-5 w-40" />
                    <Skeleton className="h-5 w-full" />
                    <Skeleton className="h-1 w-full" />
                  </div>
                ))}
              </div>
            )}
          </section>
        )}
      </main>
    </>
  );
}
