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
        <input
          type="text"
          className={`w-full rounded-lg border px-4 py-2 text-sm uppercase shadow-sm focus:outline-none ${
            invalid
              ? "border-red-400 focus:border-red-500"
              : "border-gray-300 focus:border-blue-500 dark:border-gray-600"
          } bg-white dark:bg-gray-900`}
          placeholder={`輸入美股代號（目前：${selected}）`}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setInvalid(false);
          }}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        <button
          type="button"
          onClick={submit}
          className="shrink-0 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          查詢
        </button>
      </div>
      {invalid && (
        <p className="mt-1 text-xs text-red-500">格式錯誤：1–5 個大寫英文字母（如 AAPL、BRK.B）</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => onSelect(t)}
            className={`rounded-md px-2 py-0.5 text-xs ${
              t === selected
                ? "bg-blue-600 text-white"
                : "bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}
