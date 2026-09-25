"use client";

import { createLocalStore } from "@/lib/local-store";

export type Theme = "dark" | "light";

// 與 globals.css 的 --background 同值；網址列／狀態列顏色跟著主題走
export const THEME_BACKGROUND: Record<Theme, string> = { dark: "#0d1520", light: "#f3f6f9" };

/** 預設深色（行情板）；只有明確選過淺色才用淺色 */
export const themeStore = createLocalStore<Theme>("theme", (raw) => (raw === "light" ? "light" : "dark"), "dark");

/** 首次繪製前套用主題（layout 內嵌），避免深淺閃爍 */
export const THEME_BOOT_SCRIPT = `(function(){var t="dark";try{if(localStorage.getItem("theme")==="light")t="light"}catch(e){}document.documentElement.setAttribute("data-theme",t)})();`;

export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  document.querySelectorAll('meta[name="theme-color"]').forEach((m) => m.setAttribute("content", THEME_BACKGROUND[theme]));
}

export function setTheme(theme: Theme) {
  themeStore.set(theme);
  applyTheme(theme);
}
