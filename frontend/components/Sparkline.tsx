/**
 * 近 5 個交易日的情緒走勢（純 SVG）。縱軸固定 −1 ~ +1，虛線是前 20 日基準平均；
 * 當日無標題（score = null）的點不畫、線在那裡斷開，不以 0 補值。
 */

import type { DailySentimentPoint } from "@/lib/api";

const W = 100;
const H = 36;
const y = (score: number) => H / 2 - score * (H / 2 - 3);

export default function Sparkline({
  points,
  baseline,
  strokeClass,
}: {
  points: DailySentimentPoint[];
  baseline: number | null;
  strokeClass: string; // 最後一點（當日）的顏色，對應示警等級
}) {
  if (points.length === 0) return null;
  const step = points.length > 1 ? W / (points.length - 1) : 0;
  const xy = points.map((p, i) => (p.score == null ? null : { x: i * step, y: y(p.score) }));

  // 連續有值的點才連線
  const segments: string[] = [];
  let current: string[] = [];
  xy.forEach((pt) => {
    if (pt) current.push(`${pt.x},${pt.y}`);
    else if (current.length) {
      segments.push(current.join(" "));
      current = [];
    }
  });
  if (current.length) segments.push(current.join(" "));

  const last = xy[xy.length - 1];

  return (
    <div>
      <svg viewBox={`-3 0 ${W + 6} ${H}`} preserveAspectRatio="none" className="h-9 w-full overflow-visible" aria-hidden="true">
        <line x1={0} x2={W} y1={H / 2} y2={H / 2} className="stroke-border" strokeWidth="1" vectorEffect="non-scaling-stroke" />
        {baseline != null && (
          <line
            x1={0}
            x2={W}
            y1={y(baseline)}
            y2={y(baseline)}
            className="stroke-ink-3"
            strokeWidth="1"
            strokeDasharray="3 3"
            vectorEffect="non-scaling-stroke"
          />
        )}
        {segments.map((s) =>
          s.includes(" ") ? (
            <polyline key={s} points={s} fill="none" className="stroke-ink-2" strokeWidth="1.5" vectorEffect="non-scaling-stroke" />
          ) : null,
        )}
        {last && (
          <line
            x1={last.x}
            x2={last.x}
            y1={last.y - 0.01}
            y2={last.y + 0.01}
            className={strokeClass}
            strokeWidth="7"
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>
      <div className="mt-1 flex justify-between font-mono text-meta tabular-nums text-ink-3">
        <span>{points[0].session.slice(5)}</span>
        <span>{points[points.length - 1].session.slice(5)}</span>
      </div>
    </div>
  );
}
