"use client";

/** 新聞：目前標的的完整新聞列表，篩選晶片固定在頂列下方。 */

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
      <main className="mx-auto w-full max-w-3xl px-4 pb-6 lg:px-8">
        {news ? (
          <NewsList
            articles={news.articles}
            withFilters
            filterBarClassName="sticky top-[calc(env(safe-area-inset-top)+3.5rem)] z-10 -mx-4 bg-background px-4 lg:-mx-8 lg:px-8"
          />
        ) : !error ? (
          <div className="space-y-4 pt-4">
            <Skeleton className="h-11 w-full" />
            {Array.from({ length: 6 }, (_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : null}
      </main>
    </>
  );
}
