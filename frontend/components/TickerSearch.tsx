"use client";

/**
 * 美股代號輸入：大寫化 + 前端預先驗證格式（與後端 deps.py 同一正規），
 * 明顯錯誤在前端就擋下，減少一次 422 往返。
 */

import { useState } from "react";
import { TICKER_PATTERN } from "@/lib/api";

const SUGGESTIONS = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "AMZN"];

export default function TickerSearch({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (ticker: string) => void;
}) {
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);

  const submit = () => {
    const t = value.trim().toUpperCase();
    if (!t) return;
    if (!TICKER_PATTERN.test(t)) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    onSelect(t);
    setValue("");
  };

  return (
    <div className="w-full max-w-sm">
      <div className="flex gap-2">
        <div className="relative flex-1">
          <svg
            className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-3"
            width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
          >
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
          <input
            type="text"
            className="w-full rounded-lg border bg-surface py-2 pl-9 pr-3 text-sm uppercase shadow-sm outline-none transition focus:border-accent"
            style={{ borderColor: invalid ? "var(--neg)" : "var(--border)" }}
            placeholder={`代號（目前：${selected}）`}
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setInvalid(false);
            }}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
        </div>
        <button
          type="button"
          onClick={submit}
          className="shrink-0 rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-accent-fg shadow-sm transition hover:opacity-90"
        >
          查詢
        </button>
      </div>
      {invalid && (
        <p className="mt-1 text-xs text-neg">格式錯誤：1–5 個大寫英文字母（如 AAPL、BRK.B）</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => onSelect(t)}
            className="rounded-md px-2 py-0.5 text-xs font-medium transition"
            style={
              t === selected
                ? { background: "var(--accent)", color: "var(--accent-fg)" }
                : { background: "var(--surface-2)", color: "var(--ink-2)" }
            }
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}
