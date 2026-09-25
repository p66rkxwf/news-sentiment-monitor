/**
 * 台股預警的單檔卡片：等級、z 值、近 5 日走勢、當日最負面的證據標題（最多 3 則，供人工覆核）。
 * 紅／琥珀代表示警等級，不代表漲跌方向（台股慣例漲紅跌綠，與美股分頁相反）。
 * 台股代號過不了 /api/stocks 的代號驗證，所以不連到美股的總覽與新聞頁。
 */

import Sparkline from "@/components/Sparkline";
import type { AlertLevel, StockAlert } from "@/lib/api";
import { shortTime, signed } from "@/lib/format";

export const LEVEL: Record<AlertLevel, { text: string; badge: string; value: string; stroke: string }> = {
  high: { text: "高度異常", badge: "bg-neg-soft text-neg", value: "text-neg", stroke: "stroke-neg" },
  watch: { text: "留意", badge: "bg-warn-soft text-warn", value: "text-warn", stroke: "stroke-warn" },
  normal: { text: "正常", badge: "bg-surface-2 text-ink-2", value: "text-ink", stroke: "stroke-ink" },
  insufficient: { text: "資料不足", badge: "bg-surface-2 text-ink-3", value: "text-ink-3", stroke: "stroke-ink-3" },
};

export default function AlertCard({ alert }: { alert: StockAlert }) {
  const lv = LEVEL[alert.level];
  const triggered = alert.level === "high" || alert.level === "watch";

  return (
    <li className="border-b border-border py-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="flex items-baseline gap-2">
            <span className="text-body font-semibold text-ink">{alert.name}</span>
            <span className="font-mono text-meta text-ink-3">{alert.ticker.replace(/\.TW$/, "")}</span>
          </p>
          <span className={`mt-2 inline-block rounded px-2 py-0.5 text-meta font-semibold ${lv.badge}`}>{lv.text}</span>
        </div>
        {alert.z_score != null && (
          <div className="text-right">
            <p className={`font-mono text-title font-semibold tabular-nums ${lv.value}`}>{signed(alert.z_score)}</p>
            <p className="text-meta text-ink-3">z 值</p>
          </div>
        )}
      </div>

      {alert.level === "insufficient" ? (
        <p className="mt-3 text-meta text-ink-3">{alert.reason ?? "資料不足，無法判斷。"}</p>
      ) : (
        <div className="mt-4 grid grid-cols-[minmax(0,1fr)_auto] items-start gap-6 sm:grid-cols-[minmax(0,20rem)_auto] sm:justify-between">
          <Sparkline points={alert.recent} baseline={alert.baseline_mean} strokeClass={lv.stroke} />
          <dl className="grid grid-cols-[auto_auto] gap-x-3 gap-y-0.5 text-meta">
            <dt className="text-ink-3">當日</dt>
            <dd className="text-right font-mono tabular-nums text-ink">{signed(alert.score_today)}</dd>
            <dt className="text-ink-3">基準</dt>
            <dd className="text-right font-mono tabular-nums text-ink-2">{signed(alert.baseline_mean)}</dd>
            <dt className="text-ink-3">標題</dt>
            <dd className="text-right font-mono tabular-nums text-ink-2">{alert.article_count}</dd>
          </dl>
        </div>
      )}

      {alert.evidence.length > 0 && (
        <details className="group mt-3" open={triggered}>
          <summary className="flex min-h-11 cursor-pointer list-none items-center text-meta text-accent [&::-webkit-details-marker]:hidden">
            <span className="group-open:hidden">看證據標題（{alert.evidence.length} 則）</span>
            <span className="hidden group-open:inline">收起證據標題</span>
          </summary>
          <ul className="space-y-3 border-l border-border pl-3">
            {alert.evidence.map((e) => (
              <li key={`${e.title}-${e.published_at}`}>
                <p className="text-body text-ink">{e.title}</p>
                <p className="mt-0.5 flex flex-wrap gap-x-4 text-meta text-ink-3">
                  <span>{e.source}</span>
                  <span className="font-mono tabular-nums">{shortTime(e.published_at)}</span>
                  <span>
                    分數 <span className="font-mono tabular-nums text-ink-2">{signed(e.score)}</span>
                  </span>
                </p>
              </li>
            ))}
          </ul>
        </details>
      )}
    </li>
  );
}
