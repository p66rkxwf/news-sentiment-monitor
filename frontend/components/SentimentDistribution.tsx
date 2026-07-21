/**
 * 情緒分佈條：把近期新聞逐則的情緒標籤匯總成一條分段長條。
 * 狀態型配色（正綠/中灰/負紅），每段附文字與則數，段間留 2px surface 間隙。
 */

import type { NewsItem } from "@/lib/api";

type Seg = { key: "positive" | "neutral" | "negative"; text: string; varName: string };
const SEGS: Seg[] = [
  { key: "positive", text: "正面", varName: "--pos" },
  { key: "neutral", text: "中性", varName: "--neu" },
  { key: "negative", text: "負面", varName: "--neg" },
];

export default function SentimentDistribution({ articles }: { articles: NewsItem[] }) {
  const total = articles.length;
  const counts = {
    positive: articles.filter((a) => a.sentiment === "positive").length,
    neutral: articles.filter((a) => a.sentiment === "neutral").length,
    negative: articles.filter((a) => a.sentiment === "negative").length,
  };

  if (total === 0) {
    return <p className="text-sm text-ink-3">目前沒有可統計的新聞。</p>;
  }

  return (
    <div>
      <div className="flex h-7 w-full gap-0.5 overflow-hidden rounded-lg">
        {SEGS.map((s) => {
          const c = counts[s.key];
          if (c === 0) return null;
          const pct = (c / total) * 100;
          return (
            <div
              key={s.key}
              className="flex items-center justify-center text-[11px] font-semibold text-white transition-all"
              style={{ width: `${pct}%`, background: `var(${s.varName})`, minWidth: c > 0 ? "28px" : 0 }}
              title={`${s.text} ${c} 則（${pct.toFixed(0)}%）`}
            >
              {pct >= 12 ? c : ""}
            </div>
          );
        })}
      </div>
      <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1">
        {SEGS.map((s) => (
          <div key={s.key} className="flex items-center gap-1.5 text-xs text-ink-2">
            <span className="h-2.5 w-2.5 rounded-sm" style={{ background: `var(${s.varName})` }} />
            <span>{s.text}</span>
            <span className="font-semibold tabular-nums text-ink">{counts[s.key]}</span>
            <span className="text-ink-3">({total ? Math.round((counts[s.key] / total) * 100) : 0}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}
