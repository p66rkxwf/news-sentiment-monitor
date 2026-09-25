/**
 * 追蹤清單的情緒比較：每檔一列，長條以 0 為中心向左（負）右（正）延伸——極性型編碼。
 * 資料由 app-state 抓（本次開啟只抓一次）；這裡只負責呈現。美股沒有歷史分數，故不畫走勢。
 */

import type { WatchRow } from "@/lib/app-state";
import { LABEL_TEXT, LABEL_TOKEN, signed } from "@/lib/format";

const TEXT = { pos: "text-pos", neu: "text-neu", neg: "text-neg" } as const;
const BG = { pos: "bg-pos", neu: "bg-neu", neg: "bg-neg" } as const;

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
    <ul className="divide-y divide-border">
      {rows.map(({ ticker, sentiment }) => {
        const active = ticker === selected;
        return (
          <li key={ticker}>
            <button
              type="button"
              onClick={() => onSelect(ticker)}
              aria-current={active ? "true" : undefined}
              className="grid min-h-16 w-full grid-cols-[5rem_minmax(0,1fr)_4.5rem] items-center gap-4 py-2 text-left"
            >
              <span>
                <span className={`block font-mono text-body font-semibold ${active ? "text-accent" : "text-ink"}`}>
                  {ticker}
                </span>
                <span className="block text-meta text-ink-3">
                  {sentiment ? `${sentiment.article_count} 則新聞` : active ? "目前檢視" : " "}
                </span>
              </span>

              {sentiment ? (
                <>
                  <span className="relative h-4" aria-hidden="true">
                    <span className="absolute left-1/2 top-0 h-full w-px bg-border" />
                    <span
                      className={`absolute top-1/2 h-2 -translate-y-1/2 rounded-full ${BG[LABEL_TOKEN[sentiment.label]]}`}
                      style={{
                        width: `${(Math.min(1, Math.abs(sentiment.score)) / 2) * 100}%`,
                        left: sentiment.score >= 0 ? "50%" : undefined,
                        right: sentiment.score < 0 ? "50%" : undefined,
                      }}
                    />
                  </span>
                  <span className="text-right">
                    <span className={`block font-mono text-body font-semibold tabular-nums ${TEXT[LABEL_TOKEN[sentiment.label]]}`}>
                      {signed(sentiment.score)}
                    </span>
                    <span className="block text-meta text-ink-3">{LABEL_TEXT[sentiment.label]}</span>
                  </span>
                </>
              ) : (
                <span className="col-span-2 text-meta text-ink-3">這檔目前抓不到資料，稍後重新整理。</span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
