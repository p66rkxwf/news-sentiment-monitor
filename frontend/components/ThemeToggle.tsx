"use client";

/** 深色／淺色切換（設定頁）：存 localStorage，並同步 <html data-theme> 與 theme-color。預設深色。 */

import { setTheme, themeStore, type Theme } from "@/lib/theme";

const OPTIONS: { value: Theme; text: string }[] = [
  { value: "dark", text: "深色" },
  { value: "light", text: "淺色" },
];

export default function ThemeToggle() {
  const theme = themeStore.useValue();
  return (
    <div role="group" aria-label="主題" className="inline-flex rounded-md border border-border p-1">
      {OPTIONS.map((o) => {
        const active = theme === o.value;
        return (
          <button
            key={o.value}
            type="button"
            aria-pressed={active}
            onClick={() => setTheme(o.value)}
            className={`min-h-11 min-w-20 rounded px-4 text-body transition-colors ${
              active ? "bg-accent-soft font-semibold text-accent" : "text-ink-2 hover:text-ink"
            }`}
          >
            {o.text}
          </button>
        );
      })}
    </div>
  );
}
