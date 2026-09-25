"use client";

/**
 * 台股預警的單檔卡片：等級、z 值、近 5 日走勢、當日最負面的證據標題（最多 3 則，供人工覆核）。
 * 紅／琥珀代表示警等級，不代表漲跌方向（台股慣例漲紅跌綠，與美股分頁相反）。
 * 台股代號過不了 /api/stocks 的代號驗證，所以不連到美股的總覽與新聞頁。
 */

import { ChevronDown, CircleCheck, CircleHelp, Info, Siren, TriangleAlert, type LucideIcon } from "lucide-react";
import AlertTrend from "@/components/AlertTrend";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import type { AlertLevel, StockAlert } from "@/lib/api";
import { relativeTime, signed } from "@/lib/format";
import { delay } from "@/lib/motion";

export const LEVEL: Record<
  AlertLevel,
  { text: string; badge: string; value: string; color: string; Icon: LucideIcon }
> = {
  high: { text: "高度異常", badge: "bg-neg-soft text-neg", value: "text-neg", color: "var(--neg)", Icon: Siren },
  watch: { text: "留意", badge: "bg-warn-soft text-warn", value: "text-warn", color: "var(--warn)", Icon: TriangleAlert },
  normal: { text: "正常", badge: "bg-surface-2 text-ink-2", value: "text-ink", color: "var(--brand)", Icon: CircleCheck },
  insufficient: { text: "資料不足", badge: "bg-surface-2 text-ink-3", value: "text-ink-3", color: "var(--ink-3)", Icon: CircleHelp },
};

export default function AlertCard({ alert, index = 0 }: { alert: StockAlert; index?: number }) {
  const lv = LEVEL[alert.level];
  const triggered = alert.level === "high" || alert.level === "watch";

  return (
    <li className="card animate-rise overflow-hidden" style={delay(index, 0, 40)}>
      {triggered && <div className="h-1" style={{ background: lv.color }} />}
      <div className="p-5">
        <div className="flex items-start gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-surface-2 text-body font-semibold text-ink">
            {alert.name.slice(0, 1)}
          </span>
          <div className="min-w-0 flex-1">
            <p className="flex items-baseline gap-2">
              <span className="truncate text-body font-semibold text-ink">{alert.name}</span>
              <span className="font-mono text-meta text-ink-3">{alert.ticker.replace(/\.TW$/, "")}</span>
            </p>
            <span className={`mt-1 inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-meta font-semibold ${lv.badge}`}>
              <lv.Icon size={12} strokeWidth={2.4} />
              {lv.text}
            </span>
          </div>
          {alert.z_score != null && (
            <div className="text-right">
              <p className={`font-mono text-title font-semibold tabular-nums ${lv.value}`}>{signed(alert.z_score)}</p>
              <p className="text-meta text-ink-3">z 值</p>
            </div>
          )}
        </div>

        {alert.level === "insufficient" ? (
          <p className="mt-4 flex items-start gap-2 rounded-xl bg-surface-2 px-3 py-2.5 text-meta text-ink-3">
            <Info size={14} className="mt-0.5 shrink-0" />
            {alert.reason ?? "資料不足，無法判斷。"}
          </p>
        ) : (
          <>
            <dl className="mt-4 grid grid-cols-3 gap-2">
              {(
                [
                  ["當日分數", signed(alert.score_today)],
                  ["20 日基準", signed(alert.baseline_mean)],
                  ["當日標題", `${alert.article_count} 則`],
                ] as const
              ).map(([k, v]) => (
                <div key={k} className="rounded-xl bg-surface-2 px-3 py-2">
                  <dt className="text-meta text-ink-3">{k}</dt>
                  <dd className="font-mono text-body font-semibold tabular-nums text-ink">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-4">
              <AlertTrend points={alert.recent} baseline={alert.baseline_mean} color={lv.color} />
            </div>
          </>
        )}

        {alert.evidence.length > 0 && (
          <Collapsible defaultOpen={triggered} className="mt-4 rounded-xl border border-hairline">
            <CollapsibleTrigger className="group flex min-h-11 w-full items-center justify-between px-3 text-meta font-semibold text-ink-2">
              證據標題（{alert.evidence.length} 則）
              <ChevronDown size={16} className="text-ink-3 transition-transform duration-300 group-data-[state=open]:rotate-180" />
            </CollapsibleTrigger>
            <CollapsibleContent className="overflow-hidden data-[state=closed]:animate-collapsible-up data-[state=open]:animate-collapsible-down">
              <ul className="space-y-3 border-t border-hairline px-3 py-3">
                {alert.evidence.map((e) => (
                  <li key={`${e.title}-${e.published_at}`} className="flex gap-3">
                    <span className="mt-2 size-1.5 shrink-0 rounded-full" style={{ background: lv.color }} />
                    <div className="min-w-0">
                      <p className="text-body text-ink">{e.title}</p>
                      <p className="mt-0.5 flex flex-wrap gap-x-3 text-meta text-ink-3">
                        <span>{e.source}</span>
                        <span>{relativeTime(e.published_at)}</span>
                        <span>
                          分數 <span className="font-mono tabular-nums text-ink-2">{signed(e.score)}</span>
                        </span>
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            </CollapsibleContent>
          </Collapsible>
        )}
      </div>
    </li>
  );
}
