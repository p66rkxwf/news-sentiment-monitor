/**
 * 情緒指針：半圓儀表，score ∈ [−1, +1] → 指針角度 180°~0°。
 * 顏色為狀態型配色（正面綠／負面紅／中性灰，美股慣例），數值另附文字標籤。純 SVG。
 */

import type { SentimentLabel } from "@/lib/api";

const LABEL_TEXT: Record<SentimentLabel, string> = {
  negative: "負面",
  neutral: "中性",
  positive: "正面",
};

const LABEL_VAR: Record<SentimentLabel, string> = {
  negative: "var(--neg)",
  neutral: "var(--neu)",
  positive: "var(--pos)",
};

export default function SentimentGauge({
  score,
  label,
}: {
  score: number;
  label: SentimentLabel;
}) {
  const clamped = Math.max(-1, Math.min(1, score));
  const angle = Math.PI * (1 - (clamped + 1) / 2);
  const cx = 100;
  const cy = 92;
  const r = 72;
  const needleX = cx + r * 0.82 * Math.cos(angle);
  const needleY = cy - r * 0.82 * Math.sin(angle);

  const arc = (from: number, to: number) => {
    const x1 = cx + r * Math.cos(Math.PI * (1 - from));
    const y1 = cy - r * Math.sin(Math.PI * (1 - from));
    const x2 = cx + r * Math.cos(Math.PI * (1 - to));
    const y2 = cy - r * Math.sin(Math.PI * (1 - to));
    return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
  };

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 108" className="w-full max-w-[300px]">
        {/* 底軌 */}
        <path d={arc(0, 1)} stroke="var(--surface-2)" strokeWidth="13" fill="none" strokeLinecap="round" />
        {/* 三段：負面（左紅）/ 中性（灰）/ 正面（右綠） */}
        <path d={arc(0.02, 0.4)} stroke="var(--neg)" strokeWidth="13" fill="none" strokeLinecap="round" />
        <path d={arc(0.42, 0.58)} stroke="var(--neu)" strokeWidth="13" fill="none" />
        <path d={arc(0.6, 0.98)} stroke="var(--pos)" strokeWidth="13" fill="none" strokeLinecap="round" />
        {/* 指針 */}
        <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke="var(--ink)" strokeWidth="3.5" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="6" fill="var(--ink)" />
        <circle cx={cx} cy={cy} r="2.5" fill="var(--surface)" />
        <text x="16" y="106" fontSize="9.5" fill="var(--ink-3)">−1 負面</text>
        <text x="150" y="106" fontSize="9.5" fill="var(--ink-3)">正面 +1</text>
      </svg>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-4xl font-bold tabular-nums" style={{ color: LABEL_VAR[label] }}>
          {score >= 0 ? "+" : ""}
          {score.toFixed(2)}
        </span>
        <span
          className="rounded-full px-2.5 py-0.5 text-sm font-semibold"
          style={{ color: LABEL_VAR[label], background: `var(--${label === "positive" ? "pos" : label === "negative" ? "neg" : "neu"}-soft)` }}
        >
          {LABEL_TEXT[label]}
        </span>
      </div>
      <p className="mt-1.5 text-[11px] text-ink-3">配色依美股慣例（漲綠／跌紅），與台股相反</p>
    </div>
  );
}
