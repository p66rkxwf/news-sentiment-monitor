"use client";

/**
 * 新聞列表：由新到舊，每則附情緒標籤與信心、點擊開原文。
 * 完整版（新聞分頁）有情緒篩選晶片；總覽只放前幾則、不附篩選。
 */

import { useMemo, useState } from "react";
import type { NewsItem, SentimentLabel } from "@/lib/api";
import { LABEL_TEXT, LABEL_TOKEN, percent, shortTime } from "@/lib/format";

const TEXT = { pos: "text-pos", neu: "text-neu", neg: "text-neg" } as const;
const BG = { pos: "bg-pos", neu: "bg-neu", neg: "bg-neg" } as const;

type Filter = "all" | SentimentLabel;
const FILTERS: { key: Filter; text: string; active: string }[] = [
  { key: "all", text: "全部", active: "bg-accent-soft text-accent border-transparent" },
  { key: "positive", text: "正面", active: "bg-pos-soft text-pos border-transparent" },
  { key: "neutral", text: "中性", active: "bg-neu-soft text-neu border-transparent" },
  { key: "negative", text: "負面", active: "bg-neg-soft text-neg border-transparent" },
];

function byNewest(a: NewsItem, b: NewsItem) {
  return (Date.parse(b.published_at) || 0) - (Date.parse(a.published_at) || 0);
}

export default function NewsList({
  articles,
  limit,
  withFilters = false,
  filterBarClassName = "",
}: {
  articles: NewsItem[];
  limit?: number;
  withFilters?: boolean;
  filterBarClassName?: string;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const sorted = useMemo(() => [...articles].sort(byNewest), [articles]);

  if (articles.length === 0) {
    return <p className="py-4 text-body text-ink-3">這檔股票近期沒有新聞，換一檔或稍後再重新整理。</p>;
  }

  const count = (f: Filter) => (f === "all" ? sorted.length : sorted.filter((a) => a.sentiment === f).length);
  const filtered = filter === "all" ? sorted : sorted.filter((a) => a.sentiment === filter);
  const shown = limit ? filtered.slice(0, limit) : filtered;

  return (
    <div>
      {withFilters && (
        <div role="group" aria-label="依情緒篩選" className={`flex gap-2 overflow-x-auto py-2 ${filterBarClassName}`}>
          {FILTERS.map((f) => {
            const active = filter === f.key;
            return (
              <button
                key={f.key}
                type="button"
                aria-pressed={active}
                onClick={() => setFilter(f.key)}
                className={`flex min-h-11 shrink-0 items-center gap-1.5 rounded-full border px-3 text-body transition-colors ${
                  active ? `${f.active} font-semibold` : "border-border text-ink-2 hover:text-ink"
                }`}
              >
                {f.text}
                <span className="font-mono text-meta tabular-nums">{count(f.key)}</span>
              </button>
            );
          })}
        </div>
      )}

      {shown.length === 0 ? (
        <p className="py-4 text-body text-ink-3">這個分類下沒有新聞，選「全部」看其他新聞。</p>
      ) : (
        <ul className="divide-y divide-border">
          {shown.map((a, i) => {
            const token = LABEL_TOKEN[a.sentiment];
            const body = (
              <>
                <span aria-hidden="true" className={`w-0.75 shrink-0 self-stretch rounded-full ${BG[token]}`} />
                <span className="min-w-0 flex-1">
                  <span className="block text-body text-ink group-hover:text-accent">{a.title}</span>
                  <span className="mt-1 flex flex-wrap gap-x-4 text-meta">
                    <span className={TEXT[token]}>
                      {LABEL_TEXT[a.sentiment]} <span className="font-mono tabular-nums">{percent(a.confidence)}</span>
                    </span>
                    <span className="font-mono tabular-nums text-ink-3">{shortTime(a.published_at)}</span>
                  </span>
                </span>
              </>
            );
            return (
              <li key={`${a.url}-${i}`}>
                {a.url ? (
                  <a href={a.url} target="_blank" rel="noopener noreferrer" className="group flex gap-3 py-3">
                    {body}
                  </a>
                ) : (
                  <div className="flex gap-3 py-3">{body}</div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
