import type { SentimentLabel } from "@/lib/api";

const MINUS = "−"; // 真正的減號，與等寬數字對齊

/** +0.32 / −0.18；null 顯示破折號 */
export function signed(value: number | null | undefined, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "—";
  const fixed = Math.abs(value).toFixed(digits);
  if (Number(fixed) === 0) return fixed;
  return `${value > 0 ? "+" : MINUS}${fixed}`;
}

export function percent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

const TIME_FMT = new Intl.DateTimeFormat("zh-TW", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/** 使用者當地時間「09/25 14:02」；解析失敗時原樣截短 */
export function shortTime(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso.slice(0, 16).replace("T", " ") : TIME_FMT.format(d);
}

const REL_FMT = new Intl.RelativeTimeFormat("zh-TW", { numeric: "auto" });

/** 「3 小時前」「昨天」；超過一週改顯示日期時間 */
export function relativeTime(iso: string, now = Date.now()): string {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return shortTime(iso);
  const minutes = Math.round((t - now) / 60000);
  if (Math.abs(minutes) < 1) return "剛剛";
  if (Math.abs(minutes) < 60) return REL_FMT.format(minutes, "minute");
  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 24) return REL_FMT.format(hours, "hour");
  const days = Math.round(hours / 24);
  if (Math.abs(days) <= 7) return REL_FMT.format(days, "day");
  return shortTime(iso);
}

/** 新聞來源網域（去掉 www.）；網址無效時回空字串 */
export function hostname(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return "";
  }
}

export const LABEL_TEXT: Record<SentimentLabel, string> = {
  positive: "正面",
  neutral: "中性",
  negative: "負面",
};

/** 對應 globals.css 的語意色 token（pos / neu / neg） */
export const LABEL_TOKEN: Record<SentimentLabel, "pos" | "neu" | "neg"> = {
  positive: "pos",
  neutral: "neu",
  negative: "neg",
};

/** 單則新聞在刻度上的位置：與後端 aggregate.py 同一公式（正 +conf、負 −conf、中性 0） */
export function articlePosition(label: SentimentLabel, confidence: number): number {
  return label === "positive" ? confidence : label === "negative" ? -confidence : 0;
}

/** 與後端 config.SENTIMENT_LABEL_THRESHOLD 一致：|score| 超過才判正／負 */
export const LABEL_THRESHOLD = 0.15;
