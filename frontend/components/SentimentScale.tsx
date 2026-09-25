/**
 * 新聞刻度帶：−1 ~ +1 的刻度尺上，每則新聞一條細線（位置＝方向 × 信心，中性為 0），
 * 粗線是它們的平均——也就是後端 aggregate.py 算出的情緒指數。讓人看到指數是由哪些新聞撐起來的。
 * 配色依美股慣例（正綠負紅），每處另附文字。
 */

import type { NewsItem, SentimentLabel } from "@/lib/api";
import { articlePosition, LABEL_TEXT, LABEL_THRESHOLD, LABEL_TOKEN, signed } from "@/lib/format";

const TEXT = { pos: "text-pos", neu: "text-neu", neg: "text-neg" } as const;
const BG = { pos: "bg-pos", neu: "bg-neu", neg: "bg-neg" } as const;

/** 刻度值 → 橫向百分比位置 */
const at = (x: number) => `${((Math.max(-1, Math.min(1, x)) + 1) / 2) * 100}%`;

export default function SentimentScale({
  score,
  label,
  articles,
}: {
  score: number;
  label: SentimentLabel;
  articles: NewsItem[];
}) {
  const token = LABEL_TOKEN[label];
  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <p className={`font-mono text-hero font-semibold tabular-nums ${TEXT[token]}`}>{signed(score)}</p>
        <p className={`text-title font-semibold ${TEXT[token]}`}>{LABEL_TEXT[label]}</p>
      </div>

      <div
        role="img"
        aria-label={`情緒指數 ${signed(score)}，${LABEL_TEXT[label]}。刻度上標出 ${articles.length} 則新聞的個別位置。`}
        className="relative mt-6 h-16"
      >
        {/* 中性區：|指數| ≤ 門檻 */}
        <div
          className="absolute top-2 h-8 bg-neu-soft"
          style={{ left: at(-LABEL_THRESHOLD), width: `${LABEL_THRESHOLD * 100}%` }}
        />
        {articles.map((a, i) => (
          <span
            key={`${a.url}-${i}`}
            className={`absolute top-3 h-6 w-0.5 -translate-x-1/2 rounded-full opacity-60 ${BG[LABEL_TOKEN[a.sentiment]]}`}
            style={{ left: at(articlePosition(a.sentiment, a.confidence)) }}
          />
        ))}
        <div className="absolute inset-x-0 top-10 h-px bg-border" />
        {[-1, -0.5, 0, 0.5, 1].map((t) => (
          <span key={t} className="absolute top-10 h-2 w-px -translate-x-1/2 bg-ink-3" style={{ left: at(t) }} />
        ))}
        {/* 情緒指數：細線的平均 */}
        <div
          className="absolute top-0 h-12 w-1 -translate-x-1/2 rounded-full bg-ink transition-[left] duration-500 ease-out"
          style={{ left: at(score) }}
        />
      </div>

      <div className="flex justify-between font-mono text-meta tabular-nums text-ink-3">
        <span>{signed(-1, 0)}</span>
        <span>0</span>
        <span>{signed(1, 0)}</span>
      </div>

      <p className="mt-4 max-w-prose text-meta text-ink-3">
        細線是單則新聞（方向乘以信心），粗線是它們的平均，也就是情緒指數。配色依美股慣例：綠色正面、紅色負面。
      </p>
    </div>
  );
}
