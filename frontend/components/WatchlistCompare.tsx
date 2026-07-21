"use client";

/**
 * 多標的情緒比較（新功能）：對一組追蹤清單並行抓取情緒指數，橫向長條並列，
 * 點任一列切換主檢視。長條以 0 為中心向左（負）右（正）延伸——極性型編碼。
 */

import { useEffect, useState } from "react";
import { api, type SentimentLabel } from "@/lib/api";

const WATCHLIST = ["AAPL", "TSLA", "NVDA", "MSFT", "GOOG", "AMZN"];

type Row = { ticker: string; score: number; label: SentimentLabel; count: number } | { ticker: string; error: true };

const VAR: Record<SentimentLabel, string> = {
  positive: "--pos",
  negative: "--neg",
  neutral: "--neu",
};

export default function WatchlistCompare({
  selected,
  onSelect,
}: {
  selected: string;
  onSelect: (t: string) => void;
}) {
  const [rows, setRows] = useState<Row[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all(
      WATCHLIST.map((t) =>
        api
          .sentiment(t)
          .then((s) => ({ ticker: t, score: s.score, label: s.label, count: s.article_count }))
          .catch(() => ({ ticker: t, error: true as const })),
      ),
    ).then((r) => {
      if (!cancelled) setRows(r);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div>
      {rows === null ? (
        <p className="py-6 text-center text-sm text-ink-3">載入追蹤清單…</p>
      ) : (
        <ul className="space-y-1">
          {rows.map((row) => {
            const active = row.ticker === selected;
            return (
              <li key={row.ticker}>
                <button
                  type="button"
                  onClick={() => onSelect(row.ticker)}
                  className="flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition hover:bg-surface-2"
                  style={active ? { background: "var(--accent-soft)" } : undefined}
                >
                  <span className={`w-14 shrink-0 text-sm font-semibold ${active ? "text-accent" : "text-ink"}`}>
                    {row.ticker}
                  </span>
                  {"error" in row ? (
                    <span className="flex-1 text-xs text-ink-3">無資料</span>
                  ) : (
                    <>
                      {/* 中心線兩側的極性長條 */}
                      <div className="relative h-4 flex-1">
                        <div className="absolute left-1/2 top-0 h-full w-px bg-border" />
                        <div
                          className="absolute top-1/2 h-2.5 -translate-y-1/2 rounded-sm"
                          style={{
                            background: `var(${VAR[row.label]})`,
                            width: `${(Math.abs(row.score) / 2) * 100}%`,
                            left: row.score >= 0 ? "50%" : undefined,
                            right: row.score < 0 ? "50%" : undefined,
                          }}
                        />
                      </div>
                      <span
                        className="w-12 shrink-0 text-right text-xs font-semibold tabular-nums"
                        style={{ color: `var(${VAR[row.label]})` }}
                      >
                        {row.score >= 0 ? "+" : ""}
                        {row.score.toFixed(2)}
                      </span>
                    </>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="mt-2 text-[10px] text-ink-3">長條以 0 為中心，向右正面、向左負面；點選切換主檢視。</p>
    </div>
  );
}
