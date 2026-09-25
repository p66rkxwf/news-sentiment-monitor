"use client";

/**
 * 台股預警：某個交易日全池 49 檔的情緒異常（預設只列 high / watch）。
 *
 * - 交易日來自 /api/alerts/sessions；選到非交易日自動對到前一個交易日，不送出會收到 422 的日期
 * - 看過的日期存在模組層快取，切走分頁再回來不必重抓（後端限流所有端點共用）
 * - 依回測的預先聲明：固定揭露「事前示警率與隨機響鈴無法區分」，也不提供任何「精選命中日」捷徑
 */

import { CalendarDays, ChevronLeft, ChevronRight, Clock, Info, RotateCcw } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import AlertCard, { LEVEL } from "@/components/AlertCard";
import Skeleton from "@/components/Skeleton";
import StatusBanner from "@/components/StatusBanner";
import { IconButton, PageTitle, TopBar } from "@/components/TopBar";
import { api, ApiError, type AlertLevel, type AlertsResponse } from "@/lib/api";
import { press, snappy } from "@/lib/motion";

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

/** 寫入模組層快取（在元件外定義：React Compiler 不允許元件內直接改外部變數） */
function remember(patch: Partial<typeof cache>) {
  Object.assign(cache, patch);
}

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

const SUMMARY: { level: AlertLevel; label: string }[] = [
  { level: "high", label: "高度異常" },
  { level: "watch", label: "留意" },
  { level: "normal", label: "正常" },
  { level: "insufficient", label: "資料不足" },
];

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
    remember({ asOf: d });
    setAsOfState(d);
    setError(null);
  };
  const setIncludeAll = (v: boolean) => {
    remember({ includeAll: v });
    setIncludeAllState(v);
    setError(null);
  };

  useEffect(() => {
    if (cache.sessions) return;
    api
      .alertSessions()
      .then((r) => {
        remember({ sessions: r.sessions, latest: r.latest, asOf: cache.asOf ?? r.latest });
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
        remember({ results: { ...cache.results, [key]: r } });
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
      <TopBar title={<PageTitle>台股預警</PageTitle>} subtitle="49 檔台股的新聞情緒異常" />
      <StatusBanner
        error={error}
        onRetry={() => {
          setError(null);
          setRetryToken((n) => n + 1);
        }}
      />

      <main className="mx-auto w-full max-w-3xl space-y-4 px-4 pt-4 lg:px-8 lg:pt-6">
        {/* 交易日切換 */}
        <div className="card flex items-center gap-1 p-1.5">
          <IconButton label="前一個交易日" onClick={() => sessions && setAsOf(sessions[idx - 1])} disabled={idx <= 0}>
            <ChevronLeft size={20} />
          </IconButton>
          <motion.button
            type="button"
            whileTap={press}
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
            className="flex min-h-11 flex-1 items-center justify-center gap-2 rounded-xl transition-colors hover:bg-surface-2"
            aria-label={asOf ? `交易日 ${asOf}，點一下選其他日期` : "選擇交易日"}
          >
            <CalendarDays size={17} className="text-brand" />
            <span className="font-mono text-title font-semibold tabular-nums text-ink">{asOf ?? " "}</span>
            {asOf && <span className="text-meta text-ink-3">{WEEKDAY[new Date(`${asOf}T00:00:00Z`).getUTCDay()]}</span>}
          </motion.button>
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
            <ChevronRight size={20} />
          </IconButton>
        </div>

        {latest && asOf && asOf !== latest && (
          <button type="button" onClick={() => setAsOf(latest)} className="flex min-h-10 items-center gap-1.5 px-1 text-body text-brand">
            <RotateCcw size={15} /> 回到最新交易日（{latest}）
          </button>
        )}

        {data && !data.window_closed && (
          <p className="flex items-center gap-2 rounded-2xl bg-warn-soft px-4 py-2.5 text-meta text-warn">
            <Clock size={15} className="shrink-0" />
            這個交易日還沒開盤，標題仍在累積，結果可能再變。
          </p>
        )}

        {/* 四種等級的檔數；資料不足與正常分開，不混在一起 */}
        {loading ? (
          <div className="grid grid-cols-4 gap-2">
            {SUMMARY.map((s) => (
              <Skeleton key={s.level} className="h-21 rounded-2xl" />
            ))}
          </div>
        ) : data ? (
          <dl className="grid grid-cols-4 gap-2">
            {SUMMARY.map(({ level, label }) => {
              const lv = LEVEL[level];
              const n = data.summary[level];
              return (
                <div key={level} className="card flex flex-col gap-1 p-3">
                  <lv.Icon size={16} style={{ color: lv.color }} />
                  <dd className={`font-mono text-title font-semibold tabular-nums ${n > 0 ? lv.value : "text-ink-3"}`}>{n}</dd>
                  <dt className="text-meta text-ink-3">{label}</dt>
                </div>
              );
            })}
          </dl>
        ) : null}

        <p className="flex items-start gap-2.5 rounded-2xl border border-hairline bg-surface-2/60 px-4 py-3 text-meta text-ink-3">
          <Info size={15} className="mt-0.5 shrink-0 text-brand" />
          <span>
            歷史回測中，事前示警率與隨機響鈴無法區分（p = 0.983）。本頁呈現的是開盤前的即時示警與證據標題，不是提前預警。
            台股慣例漲紅跌綠，與美股分頁相反；這裡的紅色與琥珀色代表示警等級。回測紀錄見專案 docs/alert_backtest.md。
          </span>
        </p>

        {data && (
          <div role="group" aria-label="列出哪些股票" className="grid grid-cols-2 gap-1 rounded-full border border-hairline bg-surface p-1">
            {(
              [
                [false, `示警 ${data.summary.high + data.summary.watch} 檔`],
                [true, `全部 ${data.universe_size} 檔`],
              ] as const
            ).map(([all, text]) => {
              const active = includeAll === all;
              return (
                <button
                  key={text}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setIncludeAll(all)}
                  className={`relative min-h-10 rounded-full text-body transition-colors ${
                    active ? "font-semibold text-ink" : "text-ink-3 hover:text-ink-2"
                  }`}
                >
                  {active && <motion.span layoutId="alerts-scope" transition={snappy} className="absolute inset-0 rounded-full bg-surface-3" />}
                  <span className="relative">{text}</span>
                </button>
              );
            })}
          </div>
        )}

        {loading ? (
          <div className="space-y-4">
            {Array.from({ length: 2 }, (_, i) => (
              <Skeleton key={i} className="h-64 w-full rounded-2xl" />
            ))}
          </div>
        ) : data && data.alerts.length > 0 ? (
          <ul className="space-y-4">
            {data.alerts.map((a, i) => (
              <AlertCard key={a.ticker} alert={a} index={i} />
            ))}
          </ul>
        ) : data ? (
          <div className="card flex flex-col items-center gap-2 px-6 py-10 text-center">
            <span className="flex size-12 items-center justify-center rounded-full bg-pos-soft text-pos">
              <LEVEL.normal.Icon size={22} />
            </span>
            <p className="text-body text-ink">這個交易日沒有股票達到示警門檻。</p>
            {data.summary.insufficient > 0 && (
              <p className="text-meta text-ink-3">
                其中 {data.summary.insufficient} 檔資料不足、無法判斷；切到「全部」可以看到各自缺什麼。
              </p>
            )}
          </div>
        ) : null}
      </main>
    </>
  );
}
