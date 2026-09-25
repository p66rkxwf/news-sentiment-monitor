"use client";

import { createLocalStore } from "@/lib/local-store";
import { THEME_BACKGROUND, type Theme } from "@/lib/theme-constants";

export type { Theme };

/** 預設深色（行情板）；只有明確選過淺色才用淺色 */
export const themeStore = createLocalStore<Theme>("theme", (raw) => (raw === "light" ? "light" : "dark"), "dark");

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document
    .querySelectorAll('meta[name="theme-color"]')
    .forEach((m) => m.setAttribute("content", THEME_BACKGROUND[theme]));
}

export function setTheme(theme: Theme) {
  themeStore.set(theme);
  applyTheme(theme);
}
