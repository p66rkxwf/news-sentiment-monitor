"use client";

/** 追蹤：6 檔美股的情緒指數並排比較；點一檔切換標的並回到總覽。 */

import { Info, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import Skeleton from "@/components/Skeleton";
import { IconButton, PageTitle, TopBar } from "@/components/TopBar";
import WatchlistCompare from "@/components/WatchlistCompare";
import { useAppState, WATCHLIST } from "@/lib/app-state";

export default function WatchlistPage() {
  const { ticker, selectTicker, watchlist, ensureWatchlist, refreshWatchlist } = useAppState();
  const router = useRouter();

  useEffect(() => ensureWatchlist(), [ensureWatchlist]);

  return (
    <>
      <TopBar
        title={<PageTitle>追蹤清單</PageTitle>}
        subtitle={`${WATCHLIST.length} 檔美股的情緒比較`}
        actions={
          <IconButton label="重新整理" onClick={refreshWatchlist} disabled={!watchlist}>
            <RefreshCw size={19} className={watchlist ? undefined : "animate-spin"} />
          </IconButton>
        }
      />
      <main className="mx-auto w-full max-w-3xl px-4 pt-4 lg:px-8 lg:pt-6">
        {watchlist ? (
          <WatchlistCompare
            rows={watchlist}
            selected={ticker}
            onSelect={(t) => {
              selectTicker(t);
              router.push("/");
            }}
          />
        ) : (
          <div className="card divide-y divide-hairline">
            {WATCHLIST.map((t) => (
              <div key={t} className="px-4 py-3.5">
                <div className="flex items-center gap-3">
                  <Skeleton className="size-10 rounded-full" />
                  <Skeleton className="h-10 flex-1" />
                  <Skeleton className="h-10 w-16" />
                </div>
                <Skeleton className="mt-3 h-2 w-full" />
              </div>
            ))}
          </div>
        )}
        <p className="mt-4 flex items-start gap-2 px-1 text-meta text-ink-3">
          <Info size={14} className="mt-0.5 shrink-0" />
          長條以 0 為中心，向右是正面、向左是負面。點一檔會切換到它的總覽。
        </p>
      </main>
    </>
  );
}
