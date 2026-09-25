"use client";

/**
 * 新聞列表：由新到舊，每則附情緒標籤、信心條、來源網域與相對時間，點擊開原文。
 * 完整版（新聞分頁）有情緒篩選：選中的底色膠囊會滑動，切換時列表項目以 layout 動畫進出與重排。
 */

import { ExternalLink, Minus, TrendingDown, TrendingUp } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import type { NewsItem, SentimentLabel } from "@/lib/api";
import { hostname, LABEL_TEXT, LABEL_TOKEN, percent, relativeTime } from "@/lib/format";
import { delay, EASE_OUT, snappy, stagger } from "@/lib/motion";

const PILL = { pos: "bg-pos-soft text-pos", neu: "bg-neu-soft text-neu", neg: "bg-neg-soft text-neg" } as const;
const BAR = { pos: "bg-pos", neu: "bg-neu", neg: "bg-neg" } as const;
const ICON = { positive: TrendingUp, neutral: Minus, negative: TrendingDown } as const;

type Filter = "all" | SentimentLabel;
const FILTERS: { key: Filter; text: string }[] = [
  { key: "all", text: "全部" },
  { key: "positive", text: "正面" },
  { key: "neutral", text: "中性" },
  { key: "negative", text: "負面" },
];

function byNewest(a: NewsItem, b: NewsItem) {
  return (Date.parse(b.published_at) || 0) - (Date.parse(a.published_at) || 0);
}

function NewsRow({ a }: { a: NewsItem }) {
  const token = LABEL_TOKEN[a.sentiment];
  const Icon = ICON[a.sentiment];
  const host = hostname(a.url);
  const body = (
    <>
      <div className="flex items-center gap-2 text-meta">
        <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 font-semibold ${PILL[token]}`}>
          <Icon size={12} strokeWidth={2.6} />
          {LABEL_TEXT[a.sentiment]}
          <span className="font-mono tabular-nums">{percent(a.confidence)}</span>
        </span>
        <span className="min-w-0 flex-1 truncate text-ink-3">{host}</span>
        <span className="shrink-0 text-ink-3">{relativeTime(a.published_at)}</span>
      </div>
      <p className="mt-2 text-body text-ink transition-colors group-hover:text-brand">{a.title}</p>
      <div className="mt-2.5 flex items-center gap-2">
        <span className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2">
          <span className={`block h-full rounded-full ${BAR[token]}`} style={{ width: percent(a.confidence) }} />
        </span>
        {a.url && <ExternalLink size={13} className="text-ink-3 opacity-0 transition-opacity group-hover:opacity-100" />}
      </div>
    </>
  );
  return a.url ? (
    <a href={a.url} target="_blank" rel="noopener noreferrer" className="group block px-4 py-3.5 transition-colors active:bg-surface-2">
      {body}
    </a>
  ) : (
    <div className="px-4 py-3.5">{body}</div>
  );
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
        <div className={`py-3 ${filterBarClassName}`}>
          <div role="group" aria-label="依情緒篩選" className="grid grid-cols-4 gap-1 rounded-full border border-hairline bg-surface p-1">
            {FILTERS.map((f) => {
              const active = filter === f.key;
              return (
                <button
                  key={f.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setFilter(f.key)}
                  className={`relative flex min-h-10 items-center justify-center gap-1.5 rounded-full text-body transition-colors ${
                    active ? "font-semibold text-ink" : "text-ink-3 hover:text-ink-2"
                  }`}
                >
                  {active && (
                    <motion.span layoutId="news-filter" transition={snappy} className="absolute inset-0 rounded-full bg-surface-3" />
                  )}
                  <span className="relative">{f.text}</span>
                  <span className="relative font-mono text-meta tabular-nums text-ink-3">{count(f.key)}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {shown.length === 0 ? (
        <p className="py-6 text-center text-body text-ink-3">這個分類下沒有新聞，選「全部」看其他新聞。</p>
      ) : withFilters ? (
        // 有篩選才需要 layout 動畫（項目進出與重排）；它得量測版面，成本較高，所以只用在這裡
        <ul className="card divide-y divide-hairline overflow-hidden">
          <AnimatePresence mode="popLayout">
            {shown.map((a, i) => (
              <motion.li
                key={`${a.url}-${a.title}`}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0, transition: stagger(i) }}
                exit={{ opacity: 0, transition: { duration: 0.15, ease: EASE_OUT } }}
              >
                <NewsRow a={a} />
              </motion.li>
            ))}
          </AnimatePresence>
        </ul>
      ) : (
        <ul className="card divide-y divide-hairline overflow-hidden">
          {shown.map((a, i) => (
            <li key={`${a.url}-${a.title}`} className="animate-rise" style={delay(i, 80)}>
              <NewsRow a={a} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
