"use client";

/**
 * App 外框：手機（< lg）是毛玻璃底部分頁列，桌機（≥ lg）是左側欄；兩者同一組分頁。
 * 目前分頁的底色膠囊用 layoutId 在分頁間滑動；點擊有縮放回饋。
 * 分頁切換走 client-side navigation，root layout 與共用狀態不會重建。
 */

import { BellRing, Gauge, ListOrdered, Newspaper, SlidersHorizontal } from "lucide-react";
import { MotionConfig, motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect } from "react";
import { Toaster } from "sonner";
import { MarkIcon } from "@/components/icons";
import { press, snappy } from "@/lib/motion";
import { applyTheme, themeStore } from "@/lib/theme";

const TABS = [
  { href: "/", label: "總覽", Icon: Gauge },
  { href: "/news", label: "新聞", Icon: Newspaper },
  { href: "/watchlist", label: "追蹤", Icon: ListOrdered },
  { href: "/alerts", label: "預警", Icon: BellRing },
  { href: "/settings", label: "設定", Icon: SlidersHorizontal },
] as const;

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
}

const MotionLink = motion.create(Link);

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const theme = themeStore.useValue();

  // hydration 後把 theme-color 對齊實際主題（只動 DOM，不 setState）
  useEffect(() => applyTheme(theme), [theme]);

  return (
    <MotionConfig reducedMotion="user">
      <div className="statusbar-guard sticky top-0 z-40" />

      <nav aria-label="主選單" className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col px-4 py-6 lg:flex">
        <div className="mb-8 flex items-center gap-3 px-3">
          <span className="flex size-9 items-center justify-center rounded-xl bg-brand-soft text-brand">
            <MarkIcon size={20} />
          </span>
          <span className="leading-tight">
            <span className="block text-body font-semibold text-ink">新聞情緒監控</span>
            <span className="block text-meta text-ink-3">NLP 情緒分析</span>
          </span>
        </div>
        <ul className="space-y-1">
          {TABS.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href}>
                <MotionLink
                  href={href}
                  whileTap={press}
                  aria-current={active ? "page" : undefined}
                  className={`relative flex min-h-11 items-center gap-3 rounded-xl px-3 text-body transition-colors ${
                    active ? "font-semibold text-ink" : "text-ink-2 hover:text-ink"
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId="rail-active"
                      transition={snappy}
                      className="absolute inset-0 rounded-xl border border-hairline bg-surface shadow-(--shadow-card)"
                    />
                  )}
                  <Icon size={19} className={`relative ${active ? "text-brand" : ""}`} />
                  <span className="relative">{label}</span>
                </MotionLink>
              </li>
            );
          })}
        </ul>
        <p className="mt-auto px-3 text-meta text-ink-3">情緒指數僅供學術研究參考，不構成投資建議。</p>
      </nav>

      <div className="pb-nav flex min-h-dvh flex-col lg:pl-64">{children}</div>

      <nav
        aria-label="主選單"
        className="fixed inset-x-0 bottom-0 z-30 border-t border-hairline bg-background/75 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl backdrop-saturate-150 lg:hidden"
      >
        <ul className="grid h-16 grid-cols-5 px-2">
          {TABS.map(({ href, label, Icon }) => {
            const active = isActive(pathname, href);
            return (
              <li key={href} className="flex">
                <MotionLink
                  href={href}
                  whileTap={press}
                  aria-current={active ? "page" : undefined}
                  className={`relative flex flex-1 flex-col items-center justify-center gap-1 text-meta transition-colors ${
                    active ? "font-semibold text-brand" : "text-ink-3"
                  }`}
                >
                  {active && (
                    <motion.span
                      layoutId="tab-active"
                      transition={snappy}
                      className="absolute top-1.5 h-8 w-14 rounded-full bg-brand-soft"
                    />
                  )}
                  <Icon size={21} strokeWidth={active ? 2.2 : 1.8} className="relative" />
                  <span className="relative">{label}</span>
                </MotionLink>
              </li>
            );
          })}
        </ul>
      </nav>

      <Toaster
        theme={theme}
        position="top-center"
        offset="calc(env(safe-area-inset-top) + 12px)"
        toastOptions={{
          classNames: {
            toast: "!rounded-2xl !border-hairline !bg-surface !text-ink !shadow-(--shadow-float)",
            description: "!text-ink-3",
          },
        }}
      />
    </MotionConfig>
  );
}
