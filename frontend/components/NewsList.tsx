"use client";

/**
 * 新聞列表：情緒篩選晶片（全部/正面/中性/負面）+ 逐則情緒標籤與信心分數 + 原文連結。
 */

import { useMemo, useState } from "react";
import type { NewsItem, SentimentLabel } from "@/lib/api";

const BADGE: Record<SentimentLabel, { text: string; varName: string }> = {
  positive: { text: "正面", varName: "--pos" },
  neutral: { text: "中性", varName: "--neu" },
  negative: { text: "負面", varName: "--neg" },
};

type Filter = "all" | SentimentLabel;
const FILTERS: { key: Filter; text: string }[] = [
  { key: "all", text: "全部" },
  { key: "positive", text: "正面" },
  { key: "neutral", text: "中性" },
  { key: "negative", text: "負面" },
];

export default function NewsList({ articles }: { articles: NewsItem[] }) {
  const [filter, setFilter] = useState<Filter>("all");

  const counts = useMemo(
    () => ({
      all: articles.length,
      positive: articles.filter((a) => a.sentiment === "positive").length,
      neutral: articles.filter((a) => a.sentiment === "neutral").length,
      negative: articles.filter((a) => a.sentiment === "negative").length,
    }),
    [articles],
  );

  const shown = filter === "all" ? articles : articles.filter((a) => a.sentiment === filter);

  if (articles.length === 0) {
    return <p className="text-sm text-ink-3">目前沒有新聞。</p>;
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {FILTERS.map((f) => {
          const active = filter === f.key;
          const soft =
            f.key === "positive" ? "--pos" : f.key === "negative" ? "--neg" : f.key === "neutral" ? "--neu" : "--accent";
          return (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className="rounded-full border px-2.5 py-1 text-xs font-medium transition"
              style={
                active
                  ? { background: `var(${soft})`, color: "#fff", borderColor: `var(${soft})` }
                  : { background: "var(--surface-2)", color: "var(--ink-2)", borderColor: "transparent" }
              }
            >
              {f.text} <span className="tabular-nums opacity-80">{counts[f.key]}</span>
            </button>
          );
        })}
      </div>

      {shown.length === 0 ? (
        <p className="py-4 text-sm text-ink-3">此分類下沒有新聞。</p>
      ) : (
        <ul className="divide-y divide-border">
          {shown.map((a, i) => {
            const badge = BADGE[a.sentiment];
            return (
              <li key={`${a.url}-${i}`} className="flex items-start gap-3 py-3">
                <span
                  className="mt-0.5 shrink-0 rounded-md px-2 py-0.5 text-xs font-semibold"
                  style={{
                    color: `var(${badge.varName})`,
                    background: `var(${a.sentiment === "positive" ? "--pos-soft" : a.sentiment === "negative" ? "--neg-soft" : "--neu-soft"})`,
                  }}
                  title={`信心 ${(a.confidence * 100).toFixed(0)}%`}
                >
                  {badge.text} {(a.confidence * 100).toFixed(0)}%
                </span>
                <div className="min-w-0">
                  <a
                    href={a.url || undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-ink transition hover:text-accent"
                  >
                    {a.title}
                  </a>
                  <div className="mt-0.5 text-xs text-ink-3">
                    {a.published_at.slice(0, 16).replace("T", " ")}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
