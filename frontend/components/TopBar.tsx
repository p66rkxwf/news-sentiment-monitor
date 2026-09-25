"use client";

/**
 * 各分頁的頂列（固定在狀態列下方）。總覽與新聞用 TickerBar：標題就是目前標的，點它或搜尋鈕開啟 SearchSheet。
 */

import { useState } from "react";
import SearchSheet from "@/components/SearchSheet";
import { ChevronDownIcon, RefreshIcon, SearchIcon } from "@/components/icons";
import { useAppState } from "@/lib/app-state";

/** 頁面內容寬度：頂列與 main 用同一個，左右邊界才對得齊 */
export const PAGE_WIDTH = { narrow: "max-w-3xl", wide: "max-w-5xl" } as const;
export type PageWidth = keyof typeof PAGE_WIDTH;

export function TopBar({
  title,
  actions,
  width = "narrow",
}: {
  title: React.ReactNode;
  actions?: React.ReactNode;
  width?: PageWidth;
}) {
  return (
    <header className="sticky top-[env(safe-area-inset-top)] z-20 border-b border-border bg-background">
      <div className={`mx-auto flex h-14 w-full items-center gap-2 px-4 lg:px-8 ${PAGE_WIDTH[width]}`}>
        <div className="min-w-0 flex-1">{title}</div>
        {actions && <div className="-mr-2 flex items-center">{actions}</div>}
      </div>
    </header>
  );
}

export function PageTitle({ children }: { children: React.ReactNode }) {
  return <h1 className="text-title font-semibold text-ink">{children}</h1>;
}

export function IconButton({
  label,
  onClick,
  disabled,
  children,
}: {
  label: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      className="flex h-11 w-11 items-center justify-center rounded-md text-ink-2 transition-colors hover:bg-surface hover:text-ink disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function TickerBar({ width }: { width?: PageWidth }) {
  const { ticker, view, refresh } = useAppState();
  const [searching, setSearching] = useState(false);

  return (
    <>
      <TopBar
        width={width}
        title={
          <button
            type="button"
            onClick={() => setSearching(true)}
            aria-label={ticker ? `切換標的，目前是 ${ticker}` : "切換標的"}
            className="-ml-2 flex min-h-11 items-center gap-1 rounded-md px-2 text-ink hover:bg-surface"
          >
            <span className="font-mono text-title font-semibold">{ticker ?? " "}</span>
            <ChevronDownIcon size={18} className="text-ink-3" />
          </button>
        }
        actions={
          <>
            <IconButton label="重新整理" onClick={refresh} disabled={view.loading}>
              <RefreshIcon size={20} className={view.loading ? "animate-spin" : undefined} />
            </IconButton>
            <IconButton label="搜尋代號" onClick={() => setSearching(true)}>
              <SearchIcon size={20} />
            </IconButton>
          </>
        }
      />
      {searching && <SearchSheet onClose={() => setSearching(false)} />}
    </>
  );
}
