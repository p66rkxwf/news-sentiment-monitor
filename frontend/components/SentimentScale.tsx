"use client";

/**
 * 總覽主卡：情緒指數（數字滾動）＋新聞刻度帶。
 * 刻度帶：−1 ~ +1 的尺上，每則新聞一條細線（位置＝方向 × 信心，中性為 0），粗標記是它們的平均——
 * 也就是後端 aggregate.py 算出的情緒指數。配色依美股慣例（正綠負紅），每處另附文字。
 * 動態：細線依序長出（CSS keyframe，一次性進場）、標記以彈簧移動（Motion）；都只動 transform。
 */

import { Minus, Newspaper, TrendingDown, TrendingUp } from "lucide-react";
import { motion } from "motion/react";
import AnimatedNumber from "@/components/AnimatedNumber";
import type { NewsItem, SentimentLabel } from "@/lib/api";
import { articlePosition, LABEL_TEXT, LABEL_THRESHOLD, LABEL_TOKEN, relativeTime, signed } from "@/lib/format";
import { soft } from "@/lib/motion";

const TEXT = { pos: "text-pos", neu: "text-neu", neg: "text-neg" } as const;
const BG = { pos: "bg-pos", neu: "bg-neu", neg: "bg-neg" } as const;
const PILL = { pos: "bg-pos-soft text-pos", neu: "bg-neu-soft text-neu", neg: "bg-neg-soft text-neg" } as const;
const GLOW = { pos: "var(--pos)", neu: "var(--brand)", neg: "var(--neg)" } as const;
const ICON = { positive: TrendingUp, neutral: Minus, negative: TrendingDown } as const;

/** 刻度值 → 橫向百分比位置 */
const at = (x: number) => `${((Math.max(-1, Math.min(1, x)) + 1) / 2) * 100}%`;
const fmt = (v: number) => signed(v);

export default function SentimentScale({
  score,
  label,
  articles,
  articleCount,
  asOf,
}: {
  score: number;
  label: SentimentLabel;
  articles: NewsItem[];
  articleCount: number;
  asOf: string;
}) {
  const token = LABEL_TOKEN[label];
  const Icon = ICON[label];

  return (
    <section className="card relative overflow-hidden p-5 sm:p-6">
      {/* 情緒色光暈：只作氛圍，不承載資訊 */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -top-24 left-1/2 size-72 -translate-x-1/2 rounded-full opacity-25 blur-3xl transition-colors duration-700"
        style={{ background: GLOW[token] }}
      />

      <div className="relative flex items-center justify-between gap-3">
        <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-meta font-semibold ${PILL[token]}`}>
          <Icon size={14} strokeWidth={2.4} />
          整體{LABEL_TEXT[label]}
        </span>
        <span className="flex items-center gap-1.5 text-meta text-ink-3">
          <Newspaper size={13} />
          <span className="font-mono tabular-nums text-ink-2">{articleCount}</span> 則
          <span className="text-hairline">|</span>
          {relativeTime(asOf)}更新
        </span>
      </div>

      <p className="relative mt-5 text-meta text-ink-3">情緒指數</p>
      <AnimatedNumber
        value={score}
        format={fmt}
        className={`relative block font-mono text-hero font-semibold tabular-nums tracking-tight ${TEXT[token]}`}
      />

      <div
        role="img"
        aria-label={`情緒指數 ${signed(score)}，${LABEL_TEXT[label]}。刻度上標出 ${articles.length} 則新聞的個別位置。`}
        className="relative mt-7 h-16"
      >
        {/* 中性區：|指數| ≤ 門檻 */}
        <div
          className="absolute top-2 h-8 rounded-md bg-neu-soft"
          style={{ left: at(-LABEL_THRESHOLD), width: `${LABEL_THRESHOLD * 100}%` }}
        />
        {articles.map((a, i) => (
          <span
            key={`${a.url}-${i}`}
            className={`absolute top-3 h-6 w-0.5 origin-bottom -translate-x-1/2 animate-grow-y rounded-full opacity-70 ${BG[LABEL_TOKEN[a.sentiment]]}`}
            style={{
              left: at(articlePosition(a.sentiment, a.confidence)),
              animationDelay: `${150 + Math.min(i, 24) * 18}ms`,
            }}
          />
        ))}
        <div className="absolute inset-x-0 top-10 h-px bg-border" />
        {[-1, -0.5, 0, 0.5, 1].map((t) => (
          <span key={t} className="absolute top-10 h-2 w-px -translate-x-1/2 bg-ink-3" style={{ left: at(t) }} />
        ))}
        {/* 情緒指數：細線的平均。外層與容器同寬，平移百分比＝容器寬度的百分比，走 GPU 合成 */}
        <motion.div
          className="absolute inset-0"
          initial={{ x: "0%" }}
          animate={{ x: `${Math.max(-1, Math.min(1, score)) * 50}%` }}
          transition={soft}
        >
          <div className="absolute left-1/2 top-0 h-12 w-1 -translate-x-1/2 rounded-full bg-ink shadow-[0_0_12px_var(--glow)]" />
          <div className="absolute left-1/2 top-12 size-2.5 -translate-x-1/2 rotate-45 rounded-[2px] bg-ink" />
        </motion.div>
      </div>

      <div className="relative flex justify-between font-mono text-meta tabular-nums text-ink-3">
        <span>{signed(-1, 0)} 負面</span>
        <span>0</span>
        <span>正面 {signed(1, 0)}</span>
      </div>

      <p className="relative mt-4 max-w-prose text-meta text-ink-3">
        細線是單則新聞（方向乘以信心），粗線是它們的平均，也就是情緒指數。配色依美股慣例：綠色正面、紅色負面。
      </p>
    </section>
  );
}
