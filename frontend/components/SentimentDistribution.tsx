"use client";

/**
 * 情緒分佈：環狀圖（三段依序畫出）＋右側圖例。數字比標籤大（值才是重點）。
 * 環用 SVG stroke-dasharray 畫，動畫只改 dasharray，不引入圖表庫。
 */

import { motion } from "motion/react";
import type { NewsItem, SentimentLabel } from "@/lib/api";
import { LABEL_TEXT, percent } from "@/lib/format";
import { EASE_OUT } from "@/lib/motion";

const SEGS: { key: SentimentLabel; stroke: string; dot: string; text: string }[] = [
  { key: "positive", stroke: "var(--pos)", dot: "bg-pos", text: "text-pos" },
  { key: "neutral", stroke: "var(--neu)", dot: "bg-neu", text: "text-neu" },
  { key: "negative", stroke: "var(--neg)", dot: "bg-neg", text: "text-neg" },
];

const R = 40;
const C = 2 * Math.PI * R;
const GAP = 3; // 段與段之間的間隙（圓周長單位）

export default function SentimentDistribution({ articles }: { articles: NewsItem[] }) {
  const total = articles.length;
  if (total === 0) {
    return <p className="text-body text-ink-3">這段期間沒有可統計的新聞。</p>;
  }
  const counts = SEGS.map((s) => articles.filter((a) => a.sentiment === s.key).length);
  const nonEmpty = counts.filter((c) => c > 0).length;
  const lengths = counts.map((c) => (c / total) * C);
  // 每段在圓周上的起點＝前面各段長度的總和
  const starts = lengths.map((_, i) => lengths.slice(0, i).reduce((a, b) => a + b, 0));

  return (
    <div className="grid grid-cols-[7.5rem_minmax(0,1fr)] items-center gap-6">
      <div className="relative size-30">
        <svg viewBox="0 0 100 100" className="size-full -rotate-90" aria-hidden="true">
          <circle cx="50" cy="50" r={R} fill="none" stroke="var(--surface-2)" strokeWidth="11" />
          {SEGS.map((s, i) => {
            if (counts[i] === 0) return null;
            const offset = starts[i];
            const visible = Math.max(lengths[i] - (nonEmpty > 1 ? GAP : 0), 0.5);
            return (
              <motion.circle
                key={s.key}
                cx="50"
                cy="50"
                r={R}
                fill="none"
                stroke={s.stroke}
                strokeWidth="11"
                strokeDashoffset={-offset}
                initial={{ strokeDasharray: `0 ${C}` }}
                animate={{ strokeDasharray: `${visible} ${C}` }}
                transition={{ duration: 0.7, delay: 0.1 + i * 0.12, ease: EASE_OUT }}
              />
            );
          })}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-mono text-title font-semibold tabular-nums text-ink">{total}</span>
          <span className="text-meta text-ink-3">則新聞</span>
        </div>
      </div>

      <dl className="space-y-2.5">
        {SEGS.map((s, i) => (
          <div key={s.key} className="flex items-center gap-3">
            <span className={`size-2.5 shrink-0 rounded-full ${s.dot}`} />
            <dt className="flex-1 text-body text-ink-2">{LABEL_TEXT[s.key]}</dt>
            <dd className={`font-mono text-body font-semibold tabular-nums ${s.text}`}>{counts[i]}</dd>
            <dd className="w-10 text-right font-mono text-meta tabular-nums text-ink-3">{percent(counts[i] / total)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
