"use client";

/**
 * 各分頁的頂列（毛玻璃，固定在狀態列下方）。總覽與新聞用 TickerBar：標題是目前標的，
 * 點它或搜尋鈕開啟 SearchSheet；重新整理完成會跳出提示。
 */

import { ChevronDown, RefreshCw, Search } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";
import SearchSheet from "@/components/SearchSheet";
import { useAppState } from "@/lib/app-state";
import { press } from "@/lib/motion";

/** 頁面內容寬度：頂列與 main 用同一個，左右邊界才對得齊 */
export const PAGE_WIDTH = { narrow: "max-w-3xl", wide: "max-w-6xl" } as const;
export type PageWidth = keyof typeof PAGE_WIDTH;

export function TopBar({
  title,
  subtitle,
  actions,
  width = "narrow",
}: {
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
  width?: PageWidth;
}) {
  return (
    <header className="sticky top-[env(safe-area-inset-top)] z-20 border-b border-hairline bg-background/75 backdrop-blur-xl backdrop-saturate-150">
      <div className={`mx-auto flex h-16 w-full items-center gap-2 px-4 lg:px-8 ${PAGE_WIDTH[width]}`}>
        <div className="min-w-0 flex-1">
          {title}
          {subtitle && <div className="text-meta text-ink-3">{subtitle}</div>}
        </div>
        {actions && <div className="-mr-2 flex items-center gap-1">{actions}</div>}
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
    <motion.button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      disabled={disabled}
      whileTap={press}
      className="flex size-11 items-center justify-center rounded-full text-ink-2 transition-colors hover:bg-surface-2 hover:text-ink disabled:opacity-50"
    >
      {children}
    </motion.button>
  );
}

export function TickerBar({ width }: { width?: PageWidth }) {
  const { ticker, view, refresh } = useAppState();
  const [searching, setSearching] = useState(false);

  const onRefresh = () => {
    const pending = refresh();
    if (!pending || !ticker) return;
    pending.then((ok) =>
      ok ? toast.success(`${ticker} 已更新`, { duration: 1800 }) : toast.error(`${ticker} 更新失敗，請看頁面上的說明`),
    );
  };

  return (
    <>
      <TopBar
        width={width}
        title={
          <motion.button
            type="button"
            whileTap={press}
            onClick={() => setSearching(true)}
            aria-label={ticker ? `切換標的，目前是 ${ticker}` : "切換標的"}
            className="-ml-2 flex min-h-11 items-center gap-2 rounded-full py-1 pl-2 pr-3 text-ink transition-colors hover:bg-surface-2"
          >
            <span className="flex size-8 items-center justify-center rounded-full bg-brand-soft font-mono text-meta font-semibold text-brand">
              {ticker?.slice(0, 1) ?? " "}
            </span>
            <span className="font-mono text-title font-semibold">{ticker ?? " "}</span>
            <ChevronDown size={18} className="text-ink-3" />
          </motion.button>
        }
        actions={
          <>
            <IconButton label="重新整理" onClick={onRefresh} disabled={view.loading}>
              <RefreshCw size={19} className={view.loading ? "animate-spin" : undefined} />
            </IconButton>
            <IconButton label="搜尋代號" onClick={() => setSearching(true)}>
              <Search size={19} />
            </IconButton>
          </>
        }
      />
      <SearchSheet open={searching} onOpenChange={setSearching} />
    </>
  );
}
