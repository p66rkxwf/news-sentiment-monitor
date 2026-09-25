"use client";

/** 新聞：目前標的的完整新聞列表，篩選列固定在頂列下方。 */

import NewsList from "@/components/NewsList";
import Skeleton from "@/components/Skeleton";
import StatusBanner from "@/components/StatusBanner";
import { TickerBar } from "@/components/TopBar";
import { useAppState } from "@/lib/app-state";

export default function NewsPage() {
  const { view, refresh } = useAppState();
  const { news, error } = view;

  return (
    <>
      <TickerBar />
      <StatusBanner error={error} stale={news?.stale} mock={news?.is_mock} onRetry={refresh} />
      <main className="mx-auto w-full max-w-3xl px-4 lg:px-8">
        {news ? (
          <NewsList
            articles={news.articles}
            withFilters
            filterBarClassName="sticky top-[calc(env(safe-area-inset-top)+4rem)] z-10 -mx-4 bg-background/80 px-4 backdrop-blur-xl lg:-mx-8 lg:px-8"
          />
        ) : !error ? (
          <div className="space-y-3 pt-3">
            <Skeleton className="h-12 w-full rounded-full" />
            <div className="card divide-y divide-hairline">
              {Array.from({ length: 7 }, (_, i) => (
                <div key={i} className="space-y-2.5 px-4 py-3.5">
                  <Skeleton className="h-5 w-40" />
                  <Skeleton className="h-5 w-full" />
                  <Skeleton className="h-1 w-full" />
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </main>
    </>
  );
}
