"use client";

/**
 * 台股預警：某個交易日全池 49 檔的情緒異常（預設只列 high / watch）。
 *
 * - 交易日來自 /api/alerts/sessions；選到非交易日自動對到前一個交易日，不送出會收到 422 的日期
 * - 看過的日期存在模組層快取，切走分頁再回來不必重抓（後端限流所有端點共用）
 * - 依回測的預先聲明：固定揭露「事前示警率與隨機響鈴無法區分」，也不提供任何「精選命中日」捷徑
 */

import { useEffect, useRef, useState } from "react";
import AlertCard from "@/components/AlertCard";
import { ChevronLeftIcon, ChevronRightIcon } from "@/components/icons";
import Skeleton from "@/components/Skeleton";
import StatusBanner from "@/components/StatusBanner";
import { IconButton, PageTitle, TopBar } from "@/components/TopBar";
import { api, ApiError, type AlertsResponse } from "@/lib/api";

const WEEKDAY = ["週日", "週一", "週二", "週三", "週四", "週五", "週六"];

type Key = `${string}|${"triggered" | "all"}`;
const keyOf = (asOf: string, includeAll: boolean): Key => `${asOf}|${includeAll ? "all" : "triggered"}`;

// 模組層快取：分頁元件卸載後仍保留（同一次開啟內有效）
const cache: {
  sessions: string[] | null;
  latest: string | null;
  asOf: string | null;
  includeAll: boolean;
  results: Partial<Record<Key, AlertsResponse>>;
} = { sessions: null, latest: null, asOf: null, includeAll: false, results: {} };

function describe(e: unknown): string {
  if (e instanceof ApiError && e.code === "ALERT_DATA_UNAVAILABLE") {
    return "預警分數庫是空的：先執行 alert_recorder 抓新聞並評分。";
  }
  if (e instanceof ApiError && e.status === 429) return "查詢太頻繁，請等一分鐘再試";
  return e instanceof Error ? e.message : "發生未知錯誤，請重新整理";
}

/** 最後一個 ≤ day 的交易日；day 早於第一個交易日時回第一個 */
function snapToSession(sessions: string[], day: string): string {
  let pick = sessions[0];
  for (const s of sessions) {
    if (s <= day) pick = s;
    else break;
  }
  return pick;
}

export default function AlertsPage() {
  const [sessions, setSessions] = useState(cache.sessions);
  const [latest, setLatest] = useState(cache.latest);
  const [asOf, setAsOfState] = useState(cache.asOf);
  const [includeAll, setIncludeAllState] = useState(cache.includeAll);
  const [results, setResults] = useState(cache.results);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);
  const dateInput = useRef<HTMLInputElement>(null);

  const setAsOf = (d: string) => {
    cache.asOf = d;
    setAsOfState(d);
    setError(null);
  };
  const setIncludeAll = (v: boolean) => {
    cache.includeAll = v;
    setIncludeAllState(v);
    setError(null);
  };

  useEffect(() => {
    if (cache.sessions) return;
    api
      .alertSessions()
      .then((r) => {
        cache.sessions = r.sessions;
        cache.latest = r.latest;
        cache.asOf ??= r.latest;
        setSessions(r.sessions);
        setLatest(r.latest);
        setAsOfState(cache.asOf);
      })
      .catch((e: unknown) => setError(describe(e)));
  }, [retryToken]);

  const key = asOf ? keyOf(asOf, includeAll) : null;
  const data = key ? results[key] : undefined;

  useEffect(() => {
    if (!asOf || !key || cache.results[key]) return;
    let cancelled = false;
    api
      .alerts(asOf, includeAll)
      .then((r) => {
        cache.results = { ...cache.results, [key]: r };
        if (!cancelled) setResults(cache.results);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(describe(e));
      });
    return () => {
      cancelled = true;
    };
  }, [asOf, includeAll, key, retryToken]);

  const idx = sessions && asOf ? sessions.indexOf(asOf) : -1;
  const loading = !error && !data;

  return (
    <>
      <TopBar title={<PageTitle>台股預警</PageTitle>} />
      <StatusBanner
        error={error}
        onRetry={() => {
          setError(null);
          setRetryToken((n) => n + 1);
        }}
      />

      <main className="mx-auto w-full max-w-3xl px-4 pb-6 lg:px-8">
        {/* 交易日切換 */}
        <div className="flex items-center gap-2 border-b border-border py-3">
          <IconButton label="前一個交易日" onClick={() => sessions && setAsOf(sessions[idx - 1])} disabled={idx <= 0}>
            <ChevronLeftIcon size={20} />
          </IconButton>
          <button
            type="button"
            disabled={!sessions}
            onClick={() => {
              const el = dateInput.current;
              if (!el) return;
              try {
                el.showPicker();
              } catch {
                el.focus();
              }
            }}
            className="flex min-h-11 flex-1 items-baseline justify-center gap-2 rounded-md hover:bg-surface"
            aria-label={asOf ? `交易日 ${asOf}，點一下選其他日期` : "選擇交易日"}
          >
            <span className="font-mono text-title font-semibold tabular-nums text-ink">{asOf ?? " "}</span>
            {asOf && <span className="text-meta text-ink-3">{WEEKDAY[new Date(`${asOf}T00:00:00Z`).getUTCDay()]}</span>}
          </button>
          <input
            ref={dateInput}
            type="date"
            tabIndex={-1}
            aria-hidden="true"
            className="sr-only"
            min={sessions?.[0]}
            max={sessions?.[sessions.length - 1]}
            value={asOf ?? ""}
            onChange={(e) => sessions && e.target.value && setAsOf(snapToSession(sessions, e.target.value))}
          />
          <IconButton
            label="後一個交易日"
            onClick={() => sessions && setAsOf(sessions[idx + 1])}
            disabled={!sessions || idx < 0 || idx >= sessions.length - 1}
          >
            <ChevronRightIcon size={20} />
          </IconButton>
        </div>
        {latest && asOf && asOf !== latest && (
          <button type="button" onClick={() => setAsOf(latest)} className="mt-2 min-h-11 text-body text-accent hover:underline">
            回到最新交易日（{latest}）
          </button>
        )}

        {data && !data.window_closed && (
          <p className="mt-4 rounded-md bg-warn-soft px-4 py-2 text-meta text-warn">
            這個交易日還沒開盤，標題仍在累積，結果可能再變。
          </p>
        )}

        {/* 四種等級的檔數 */}
        {loading ? (
          <Skeleton className="mt-4 h-16 w-full" />
        ) : data ? (
          <dl className="mt-4 grid grid-cols-4 gap-2 border-b border-border pb-4">
            {(
              [
                ["高度異常", data.summary.high, "text-neg"],
                ["留意", data.summary.watch, "text-warn"],
                ["正常", data.summary.normal, "text-ink"],
                ["資料不足", data.summary.insufficient, "text-ink-3"],
              ] as const
            ).map(([label, n, cls]) => (
              <div key={label}>
                <dt className="text-meta text-ink-3">{label}</dt>
                <dd className={`font-mono text-title font-semibold tabular-nums ${cls}`}>{n}</dd>
              </div>
            ))}
          </dl>
        ) : null}

        <p className="mt-4 max-w-prose border-l-2 border-border pl-3 text-meta text-ink-3">
          歷史回測中，事前示警率與隨機響鈴無法區分（p = 0.983）。本頁呈現的是開盤前的即時示警與證據標題，不是提前預警。
          台股慣例漲紅跌綠，與美股分頁相反；這裡的紅色與琥珀色代表示警等級。回測紀錄見專案 docs/alert_backtest.md。
        </p>

        {data && (
          <div className="mt-4 flex items-center justify-between border-b border-border pb-2">
            <p className="text-body text-ink-2">
              {includeAll ? `全部 ${data.universe_size} 檔` : `示警 ${data.summary.high + data.summary.watch} 檔`}
            </p>
            <button
              type="button"
              aria-pressed={includeAll}
              onClick={() => setIncludeAll(!includeAll)}
              className="min-h-11 rounded-md px-3 text-body text-accent hover:bg-surface"
            >
              {includeAll ? "只看示警" : `顯示全部 ${data.universe_size} 檔`}
            </button>
          </div>
        )}

        {loading ? (
          <div className="space-y-4 pt-4">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
        ) : data && data.alerts.length > 0 ? (
          <ul>
            {data.alerts.map((a) => (
              <AlertCard key={a.ticker} alert={a} />
            ))}
          </ul>
        ) : data ? (
          <div className="py-8 text-body text-ink-2">
            <p>這個交易日沒有股票達到示警門檻。</p>
            {data.summary.insufficient > 0 && (
              <p className="mt-2 text-meta text-ink-3">
                其中 {data.summary.insufficient} 檔資料不足、無法判斷；按「顯示全部」可以看到各自缺什麼。
              </p>
            )}
          </div>
        ) : null}
      </main>
    </>
  );
}
