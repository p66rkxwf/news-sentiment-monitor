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
