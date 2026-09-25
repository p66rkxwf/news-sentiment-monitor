"use client";

import { useSyncExternalStore } from "react";

/** 媒體查詢（useSyncExternalStore）；伺服器端與 hydration 期間回 serverValue */
export function useMediaQuery(query: string, serverValue = false): boolean {
  return useSyncExternalStore(
    (onChange) => {
      const mql = window.matchMedia(query);
      mql.addEventListener("change", onChange);
      return () => mql.removeEventListener("change", onChange);
    },
    () => window.matchMedia(query).matches,
    () => serverValue,
  );
}

/** 與 AppShell 的斷點一致：≥ 1024px 是桌機版（左側欄） */
export const useIsDesktop = () => useMediaQuery("(min-width: 64rem)");
