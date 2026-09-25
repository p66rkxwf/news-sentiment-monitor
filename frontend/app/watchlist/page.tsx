"use client";

/** 追蹤：6 檔美股的情緒指數並排比較；點一檔切換標的並回到總覽。 */

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { RefreshIcon } from "@/components/icons";
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
        actions={
          <IconButton label="重新整理" onClick={refreshWatchlist} disabled={!watchlist}>
            <RefreshIcon size={20} className={watchlist ? undefined : "animate-spin"} />
          </IconButton>
        }
      />
      <main className="mx-auto w-full max-w-3xl px-4 pb-6 lg:px-8">
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
          <div className="divide-y divide-border">
            {WATCHLIST.map((t) => (
              <div key={t} className="py-4">
                <Skeleton className="h-8 w-full" />
              </div>
            ))}
          </div>
        )}
        <p className="mt-4 text-meta text-ink-3">長條以 0 為中心，向右是正面、向左是負面。點一檔會切換到它的總覽。</p>
      </main>
    </>
  );
}
