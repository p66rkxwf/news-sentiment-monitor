"use client";

/**
 * 總覽：目前標的的情緒指數（新聞刻度帶）、情緒分佈、熱門關鍵字、最新幾則新聞。
 * 錯誤處理對應 Phase 0 凍結契約（422/404/503），訊息對照在 app-state.describeError。
 */

import Link from "next/link";
import KeywordList from "@/components/KeywordList";
import NewsList from "@/components/NewsList";
import Section from "@/components/Section";
import SentimentDistribution from "@/components/SentimentDistribution";
import SentimentScale from "@/components/SentimentScale";
import Skeleton from "@/components/Skeleton";
import StatusBanner from "@/components/StatusBanner";
import { TickerBar } from "@/components/TopBar";
import { useAppState } from "@/lib/app-state";
import { shortTime } from "@/lib/format";

const PREVIEW = 5;

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

      <main className="mx-auto w-full max-w-5xl lg:grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] lg:gap-x-12 lg:px-8">
        <div>
          <Section>
            {ready ? (
              <>
                <SentimentScale score={sentiment.score} label={sentiment.label} articles={news.articles} />
                <div className="mt-6 flex flex-wrap gap-x-6 gap-y-1 text-meta text-ink-3">
                  <span>
                    <span className="font-mono tabular-nums text-ink-2">{sentiment.article_count}</span> 則新聞
                  </span>
                  <span>
                    資料時間 <span className="font-mono tabular-nums text-ink-2">{shortTime(sentiment.as_of)}</span>
                  </span>
                </div>
              </>
            ) : firstLoad ? (
              <div className="space-y-4">
                <Skeleton className="h-11 w-40" />
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-4 w-3/4" />
              </div>
            ) : (
              <p className="py-8 text-body text-ink-3">點上方的代號換一檔，或稍後按「重試」。</p>
            )}
          </Section>

          {ready && (
            <>
              <Section title="新聞情緒分佈">
                <SentimentDistribution articles={news.articles} />
              </Section>
              <Section title="熱門關鍵字">
                <KeywordList keywords={sentiment.keywords} ticker={ticker ?? undefined} />
              </Section>
            </>
          )}
        </div>

        {(ready || firstLoad) && (
          <Section
            title="最新新聞"
            className="lg:border-b-0"
            action={
              ready && news.articles.length > PREVIEW ? (
                <Link href="/news" className="flex min-h-11 items-center text-body text-accent hover:underline">
                  看全部 {news.articles.length} 則
                </Link>
              ) : null
            }
          >
            {ready ? (
              <NewsList articles={news.articles} limit={PREVIEW} />
            ) : (
              <div className="space-y-4">
                {Array.from({ length: 4 }, (_, i) => (
                  <Skeleton key={i} className="h-12 w-full" />
                ))}
              </div>
            )}
          </Section>
        )}
      </main>
    </>
  );
}
