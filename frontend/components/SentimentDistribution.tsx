/**
 * 情緒分佈：逐則標籤匯總成一條分段長條＋三欄數字。數字比標籤大（值才是重點）。
 */

import type { NewsItem, SentimentLabel } from "@/lib/api";
import { LABEL_TEXT, percent } from "@/lib/format";

const SEGS: { key: SentimentLabel; bg: string; text: string }[] = [
  { key: "positive", bg: "bg-pos", text: "text-pos" },
  { key: "neutral", bg: "bg-neu", text: "text-neu" },
  { key: "negative", bg: "bg-neg", text: "text-neg" },
];

export default function SentimentDistribution({ articles }: { articles: NewsItem[] }) {
  const total = articles.length;
  if (total === 0) {
    return <p className="text-body text-ink-3">這段期間沒有可統計的新聞。</p>;
  }
  const count = (k: SentimentLabel) => articles.filter((a) => a.sentiment === k).length;

  return (
    <div>
      <div className="flex h-2 gap-0.5 overflow-hidden rounded-full" aria-hidden="true">
        {SEGS.map((s) => {
          const c = count(s.key);
          return c > 0 ? <div key={s.key} className={s.bg} style={{ width: `${(c / total) * 100}%` }} /> : null;
        })}
      </div>
      <dl className="mt-4 grid grid-cols-3 gap-4">
        {SEGS.map((s) => {
          const c = count(s.key);
          return (
            <div key={s.key}>
              <dt className="text-meta text-ink-3">{LABEL_TEXT[s.key]}</dt>
              <dd className={`font-mono text-title font-semibold tabular-nums ${s.text}`}>{c}</dd>
              <dd className="font-mono text-meta tabular-nums text-ink-3">{percent(c / total)}</dd>
            </div>
          );
        })}
      </dl>
    </div>
  );
}
