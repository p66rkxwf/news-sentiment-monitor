"use client";

/**
 * 靜態站的資料時效：每日排程何時更新、台股預警最新到哪個交易日。
 * 排程失敗時線上停在上一版，超過 48 小時未更新就以警示色標出，避免把過期資料當成最新。
 */

import { CalendarClock, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { siteMeta, type SiteMeta } from "@/lib/api";

const STALE_HOURS = 48;

function taipeiTime(iso: string): string {
  return new Date(iso).toLocaleString("zh-TW", {
    timeZone: "Asia/Taipei",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export default function DataFreshness() {
  const [meta, setMeta] = useState<SiteMeta | null | "error">(null);

  useEffect(() => {
    siteMeta().then(setMeta).catch(() => setMeta("error"));
  }, []);

  if (meta === null) return null;
  if (meta === "error") return <p className="px-4 py-3 text-meta text-ink-3">讀不到資料更新時間。</p>;

  const stale = Date.now() - Date.parse(meta.generated_at) > STALE_HOURS * 3600 * 1000;
  return (
    <div className="space-y-2 px-4 py-3 text-meta">
      <p className={`flex items-center gap-2 ${stale ? "text-warn" : "text-ink-2"}`}>
        {stale ? <TriangleAlert size={15} /> : <CalendarClock size={15} className="text-ink-3" />}
        每日自動更新，上次更新 {taipeiTime(meta.generated_at)}（台北時間）
        {stale && "，資料可能已過期"}
      </p>
      <p className="text-ink-3">
        台股預警最新交易日：{meta.alerts_latest ?? "準備中"}
        {meta.alerts_status === "quota" && "（今日評分額度用盡，部分標題尚未評分，明日補上）"}
        {meta.alerts_status === "failed" && "（今日台股新聞更新失敗，顯示的是前一次的結果）"}
      </p>
    </div>
  );
}
