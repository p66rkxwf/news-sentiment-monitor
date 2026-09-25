"use client";

/** 深色／淺色切換（設定頁）：選中的底色膠囊滑動；存 localStorage，並同步 <html data-theme> 與 theme-color。 */

import { Moon, Sun } from "lucide-react";
import { motion } from "motion/react";
import { snappy } from "@/lib/motion";
import { setTheme, themeStore, type Theme } from "@/lib/theme";

const OPTIONS: { value: Theme; text: string; Icon: typeof Moon }[] = [
  { value: "dark", text: "深色", Icon: Moon },
  { value: "light", text: "淺色", Icon: Sun },
];

export default function ThemeToggle() {
  const theme = themeStore.useValue();
  return (
    <div role="group" aria-label="主題" className="inline-grid grid-cols-2 gap-1 rounded-full border border-hairline bg-surface-2 p-1">
      {OPTIONS.map(({ value, text, Icon }) => {
        const active = theme === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            onClick={() => setTheme(value)}
            className={`relative flex min-h-10 min-w-24 items-center justify-center gap-2 rounded-full px-4 text-body transition-colors ${
              active ? "font-semibold text-ink" : "text-ink-3 hover:text-ink-2"
            }`}
          >
            {active && (
              <motion.span
                layoutId="theme-pill"
                transition={snappy}
                className="absolute inset-0 rounded-full bg-surface shadow-(--shadow-card)"
              />
            )}
            <Icon size={16} className="relative" />
            <span className="relative">{text}</span>
          </button>
        );
      })}
    </div>
  );
}
