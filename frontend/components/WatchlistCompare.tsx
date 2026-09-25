/**
 * 追蹤清單的情緒比較：每檔一列，長條以 0 為中心向左（負）右（正）長出——極性型編碼。
 * 資料由 app-state 抓（本次開啟只抓一次）；這裡只負責呈現。美股沒有歷史分數，故不畫走勢。
 * 進場與長條伸展都是 CSS keyframe；按下回饋用 CSS active 縮放。
 */

import { ChevronRight, Minus, TrendingDown, TrendingUp } from "lucide-react";
import type { WatchRow } from "@/lib/app-state";
import { LABEL_TEXT, LABEL_TOKEN, signed } from "@/lib/format";
import { delay } from "@/lib/motion";

const TEXT = { pos: "text-pos", neu: "text-neu", neg: "text-neg" } as const;
const BG = { pos: "bg-pos", neu: "bg-neu", neg: "bg-neg" } as const;
const ICON = { positive: TrendingUp, neutral: Minus, negative: TrendingDown } as const;

export default function WatchlistCompare({
  rows,
  selected,
  onSelect,
}: {
  rows: WatchRow[];
  selected: string | null;
  onSelect: (ticker: string) => void;
}) {
  return (
    <ul className="card divide-y divide-hairline overflow-hidden">
      {rows.map(({ ticker, sentiment }, i) => {
        const active = ticker === selected;
        const token = sentiment ? LABEL_TOKEN[sentiment.label] : "neu";
        const Icon = sentiment ? ICON[sentiment.label] : Minus;
        const magnitude = sentiment ? Math.min(1, Math.abs(sentiment.score)) : 0;
        return (
          <li key={ticker} className="animate-rise" style={delay(i)}>
            <button
              type="button"
              onClick={() => onSelect(ticker)}
              aria-current={active ? "true" : undefined}
              className={`block w-full px-4 py-3.5 text-left transition-[background-color,scale] duration-150 hover:bg-surface-2 active:scale-[0.985] ${
                active ? "bg-brand-soft" : ""
              }`}
            >
              <span className="flex items-center gap-3">
                <span
                  className={`flex size-10 shrink-0 items-center justify-center rounded-full font-mono text-meta font-semibold ${
                    active ? "bg-brand text-brand-fg" : "bg-surface-2 text-ink-2"
                  }`}
                >
                  {ticker.slice(0, 2)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-mono text-body font-semibold text-ink">{ticker}</span>
                  <span className="block text-meta text-ink-3">
                    {sentiment ? `${sentiment.article_count} 則新聞` : "這檔目前抓不到資料，稍後重新整理"}
                  </span>
                </span>
                {sentiment && (
                  <span className="text-right">
                    <span className={`block font-mono text-body font-semibold tabular-nums ${TEXT[token]}`}>
                      {signed(sentiment.score)}
                    </span>
                    <span className={`inline-flex items-center gap-0.5 text-meta ${TEXT[token]}`}>
                      <Icon size={11} strokeWidth={2.6} />
                      {LABEL_TEXT[sentiment.label]}
                    </span>
                  </span>
                )}
                <ChevronRight size={16} className="shrink-0 text-ink-3" />
              </span>

              {/* 極性長條：獨立一行、橫跨整列，小分數也看得出方向 */}
              {sentiment && (
                <span className="relative mt-3 block h-2" aria-hidden="true">
                  <span className="absolute inset-0 rounded-full bg-surface-2" />
                  <span className="absolute -top-1 left-1/2 h-4 w-px bg-ink-3" />
                  <span
                    className={`absolute inset-y-0 w-1/2 animate-grow-x rounded-full ${BG[token]} ${
                      sentiment.score >= 0 ? "left-1/2 origin-left" : "right-1/2 origin-right"
                    }`}
                    style={{ transform: `scaleX(${magnitude})`, ...delay(i, 120, 50) }}
                  />
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
