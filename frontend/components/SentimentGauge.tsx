/**
 * 情緒指針：半圓儀表，score ∈ [−1, +1] → 指針角度 0°~180°。
 * 顏色依美股慣例：正面綠、負面紅（與台股相反，UI 已標示）。純 SVG，不引繪圖庫。
 */

import type { SentimentLabel } from "@/lib/api";

const LABEL_TEXT: Record<SentimentLabel, string> = {
  negative: "負面",
  neutral: "中性",
  positive: "正面",
};

const LABEL_COLOR: Record<SentimentLabel, string> = {
  negative: "#dc2626", // 美股慣例：跌紅
  neutral: "#6b7280",
  positive: "#16a34a", // 美股慣例：漲綠
};

export default function SentimentGauge({
  score,
  label,
}: {
  score: number;
  label: SentimentLabel;
}) {
  const clamped = Math.max(-1, Math.min(1, score));
  // score −1 → 180°（左端），+1 → 0°（右端）；SVG 座標角度
  const angle = Math.PI * (1 - (clamped + 1) / 2);
  const cx = 100;
  const cy = 90;
  const r = 70;
  const needleX = cx + r * 0.85 * Math.cos(angle);
  const needleY = cy - r * 0.85 * Math.sin(angle);

  const arc = (from: number, to: number) => {
    const x1 = cx + r * Math.cos(Math.PI * (1 - from));
    const y1 = cy - r * Math.sin(Math.PI * (1 - from));
    const x2 = cx + r * Math.cos(Math.PI * (1 - to));
    const y2 = cy - r * Math.sin(Math.PI * (1 - to));
    return `M ${x1} ${y1} A ${r} ${r} 0 0 1 ${x2} ${y2}`;
  };

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 105" className="w-full max-w-[280px]">
        {/* 三段弧：負面（左紅）/ 中性（灰）/ 正面（右綠）—— 美股紅綠慣例 */}
        <path d={arc(0, 0.4)} stroke="#dc2626" strokeWidth="12" fill="none" strokeLinecap="round" />
        <path d={arc(0.4, 0.6)} stroke="#9ca3af" strokeWidth="12" fill="none" />
        <path d={arc(0.6, 1)} stroke="#16a34a" strokeWidth="12" fill="none" strokeLinecap="round" />
        {/* 指針 */}
        <line
          x1={cx}
          y1={cy}
          x2={needleX}
          y2={needleY}
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="5" fill="currentColor" />
        {/* 端點標示 */}
        <text x="18" y="102" fontSize="10" fill="#9ca3af">
          −1 負面
        </text>
        <text x="152" y="102" fontSize="10" fill="#9ca3af">
          +1 正面
        </text>
      </svg>
      <div className="mt-1 text-center">
        <span className="text-3xl font-bold" style={{ color: LABEL_COLOR[label] }}>
          {score >= 0 ? "+" : ""}
          {score.toFixed(2)}
        </span>
        <span className="ml-2 text-lg font-medium" style={{ color: LABEL_COLOR[label] }}>
          {LABEL_TEXT[label]}
        </span>
      </div>
      <p className="mt-1 text-[11px] text-gray-400">
        配色依美股慣例（漲綠／跌紅），與台股相反
      </p>
    </div>
  );
}
