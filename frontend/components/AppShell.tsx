"use client";

/**
 * App 外框：手機（< lg）是底部分頁列，桌機（≥ lg）是左側欄；兩者同一組分頁。
 * 分頁切換走 client-side navigation，root layout 與共用狀態不會重建。
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { AlertIcon, MarkIcon, NewsIcon, OverviewIcon, SettingsIcon, WatchlistIcon } from "@/components/icons";
import { applyTheme, themeStore } from "@/lib/theme";

const TABS = [
  { href: "/", label: "總覽", Icon: OverviewIcon },
  { href: "/news", label: "新聞", Icon: NewsIcon },
  { href: "/watchlist", label: "追蹤", Icon: WatchlistIcon },
  { href: "/alerts", label: "預警", Icon: AlertIcon },
  { href: "/settings", label: "設定", Icon: SettingsIcon },
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const theme = themeStore.useValue();

  // hydration 後把 theme-color 對齊實際主題（只動 DOM，不 setState）
  useEffect(() => applyTheme(theme), [theme]);

  return (
    <>
      <div className="statusbar-guard sticky top-0 z-40" />

      <nav
        aria-label="主選單"
        className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col border-r border-border bg-background px-3 py-6 lg:flex"
      >
        <div className="mb-8 flex items-center gap-2 px-3 text-ink">
          <MarkIcon size={24} className="text-accent" />
          <span className="text-body font-semibold">新聞情緒監控</span>
        </div>
        <ul className="space-y-1">
          {TABS.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`flex min-h-11 items-center gap-3 rounded-md px-3 text-body transition-colors ${
                    active ? "bg-accent-soft font-semibold text-accent" : "text-ink-2 hover:bg-surface hover:text-ink"
                  }`}
                >
                  <Icon size={20} />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
        <p className="mt-auto px-3 text-meta text-ink-3">情緒指數僅供學術研究參考，不構成投資建議。</p>
      </nav>

      <div className="pb-nav flex min-h-dvh flex-col lg:pl-60">{children}</div>

      <nav
        aria-label="主選單"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-background pb-[env(safe-area-inset-bottom)] lg:hidden"
      >
        <ul className="grid h-16 grid-cols-5">
          {TABS.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href}>
                <Link
                  href={href}
                  aria-current={active ? "page" : undefined}
                  className={`relative flex h-full flex-col items-center justify-center gap-1 text-meta transition-colors ${
                    active ? "font-semibold text-accent" : "text-ink-3"
                  }`}
                >
                  {active && <span className="absolute inset-x-5 top-0 h-0.5 rounded-full bg-accent" />}
                  <Icon size={22} />
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>
    </>
  );
}
