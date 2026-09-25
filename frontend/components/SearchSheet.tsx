"use client";

/**
 * 切換標的：手機全螢幕、桌機置中對話框。格式與後端 deps.py 同一條正規，錯誤格式在前端就擋下（少一次 422）。
 * 不給空白畫面：列出輸入中的代號、最近查詢與追蹤清單，點一下就切換。
 */

import { useEffect, useRef, useState } from "react";
import { SearchIcon } from "@/components/icons";
import { TICKER_PATTERN } from "@/lib/api";
import { useAppState, WATCHLIST } from "@/lib/app-state";

export default function SearchSheet({ onClose }: { onClose: () => void }) {
  const { ticker, selectTicker, recent } = useAppState();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prevOverflow;
    };
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const typed = value.trim().toUpperCase();
  const typedValid = TICKER_PATTERN.test(typed);

  const choose = (t: string) => {
    selectTicker(t);
    onClose();
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typed) return;
    if (!typedValid) {
      setInvalid(true);
      return;
    }
    choose(typed);
  };

  const groups = [
    { title: "最近查詢", tickers: recent },
    { title: "追蹤清單", tickers: WATCHLIST.filter((t) => !recent.includes(t)) },
  ].filter((g) => g.tickers.length > 0);

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="切換標的"
      className="fixed inset-0 z-50 flex flex-col bg-background lg:items-center lg:bg-black/50 lg:pt-24"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="flex min-h-0 flex-1 flex-col bg-background lg:w-full lg:max-w-md lg:flex-none lg:rounded-lg lg:border lg:border-border lg:bg-surface lg:shadow-(--shadow-float)">
        <div className="statusbar-guard lg:hidden" />
        <form
          onSubmit={submit}
          className="flex items-center gap-2 border-b border-border px-4 py-2 focus-within:border-accent"
        >
          <SearchIcon size={20} className="shrink-0 text-ink-3" />
          <input
            ref={inputRef}
            type="text"
            inputMode="text"
            autoCapitalize="characters"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="search"
            aria-label="美股代號"
            aria-invalid={invalid}
            placeholder="輸入美股代號，例如 AAPL"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setInvalid(false);
            }}
            className="min-h-11 min-w-0 flex-1 bg-transparent font-mono text-body uppercase text-ink outline-none focus-visible:outline-none placeholder:font-sans placeholder:normal-case placeholder:text-ink-3"
          />
          <button type="button" onClick={onClose} className="min-h-11 shrink-0 px-2 text-body text-accent">
            取消
          </button>
        </form>

        <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6 lg:max-h-[60vh]">
          {invalid && (
            <p role="alert" className="pt-4 text-meta text-neg">
              代號格式不對：1–5 個英文字母，可加一碼類別（例如 AAPL、BRK.B）。
            </p>
          )}

          {typed && typedValid && (
            <button
              type="button"
              onClick={() => choose(typed)}
              className="mt-2 flex min-h-12 w-full items-center gap-3 border-b border-border text-left"
            >
              <span className="text-body text-ink-2">查詢</span>
              <span className="font-mono text-body font-semibold text-ink">{typed}</span>
            </button>
          )}

          {groups.map((g) => (
            <section key={g.title} className="mt-6">
              <h2 className="mb-1 text-meta text-ink-3">{g.title}</h2>
              <ul className="divide-y divide-border">
                {g.tickers.map((t) => (
                  <li key={t}>
                    <button
                      type="button"
                      onClick={() => choose(t)}
                      className="flex min-h-12 w-full items-center justify-between text-left"
                    >
                      <span className={`font-mono text-body font-semibold ${t === ticker ? "text-accent" : "text-ink"}`}>
                        {t}
                      </span>
                      {t === ticker && <span className="text-meta text-ink-3">目前檢視</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
