"use client";

/**
 * 預警卡片的近 5 個交易日走勢（Recharts 面積圖）。縱軸固定 −1 ~ +1；虛線是前 20 日基準平均。
 * 當日無標題（score = null）的點不畫、線在那裡斷開，不以 0 補值。點或滑過可看當日分數與則數。
 */

import { useId } from "react";
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { DailySentimentPoint } from "@/lib/api";
import { signed } from "@/lib/format";

type Row = { day: string; score: number | null; n: number };

function TrendTooltip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const row = active ? payload?.[0]?.payload : undefined;
  if (!row) return null;
  return (
    <div className="rounded-xl border border-hairline bg-surface px-3 py-2 text-meta shadow-(--shadow-float)">
      <p className="font-mono tabular-nums text-ink-3">{row.day}</p>
      <p className="font-mono font-semibold tabular-nums text-ink">{row.score == null ? "當日無標題" : signed(row.score)}</p>
      <p className="text-ink-3">{row.n} 則標題</p>
    </div>
  );
}

export default function AlertTrend({
  points,
  baseline,
  color,
}: {
  points: DailySentimentPoint[];
  baseline: number | null;
  color: string; // CSS 色值（例如 var(--neg)），對應示警等級
}) {
  const gradientId = `trend-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const data: Row[] = points.map((p) => ({ day: p.session.slice(5), score: p.score, n: p.article_count }));

  return (
    <div>
      <div className="h-20 w-full">
        <ResponsiveContainer>
          <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 2, left: 6 }}>
            <defs>
              <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.35} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="day" hide />
            <YAxis domain={[-1, 1]} hide />
            <ReferenceLine y={0} stroke="var(--border)" />
            {baseline != null && <ReferenceLine y={baseline} stroke="var(--ink-3)" strokeDasharray="4 4" />}
            <Tooltip content={<TrendTooltip />} cursor={{ stroke: "var(--border)" }} />
            <Area
              type="monotone"
              dataKey="score"
              stroke={color}
              strokeWidth={2}
              fill={`url(#${gradientId})`}
              connectNulls={false}
              dot={{ r: 2.5, fill: color, strokeWidth: 0 }}
              activeDot={{ r: 4.5, fill: color, stroke: "var(--surface)", strokeWidth: 2 }}
              animationDuration={700}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-1 flex justify-between font-mono text-meta tabular-nums text-ink-3">
        <span>{data[0]?.day}</span>
        <span className="flex items-center gap-1.5 font-sans">
          <span className="inline-block w-4 border-t border-dashed border-ink-3" /> 20 日基準
        </span>
        <span>{data[data.length - 1]?.day}</span>
      </div>
    </div>
  );
}
