/**
 * 關鍵字雲：後端已算好 TF-IDF 分數，前端只做「分數 → 字級/濃淡」映射，不引繪圖庫。
 */

import type { KeywordScore } from "@/lib/api";

// 標的自家名字在自家新聞裡本來就最常出現（AAPL→apple、NVDA→nvidia…），
// 濾掉後才露出真正在被討論的其他主題。未知代號則僅濾與代號同字者。
const BRAND_ALIASES: Record<string, string[]> = {
  AAPL: ["apple"],
  TSLA: ["tesla"],
  NVDA: ["nvidia"],
  MSFT: ["microsoft"],
  GOOG: ["google", "alphabet"],
  GOOGL: ["google", "alphabet"],
  AMZN: ["amazon"],
  META: ["meta", "facebook"],
};

export default function KeywordCloud({ keywords, ticker }: { keywords: KeywordScore[]; ticker?: string }) {
  const selfWords = new Set<string>(
    ticker ? [ticker.toLowerCase(), ...(BRAND_ALIASES[ticker.toUpperCase()] ?? [])] : [],
  );
  const filtered = keywords.filter((k) => !selfWords.has(k.word.toLowerCase()));
  // 全被濾掉（極少見）就退回原始清單，避免整塊空白
  const shown = filtered.length > 0 ? filtered : keywords;

  if (shown.length === 0) {
    return <p className="text-sm text-ink-3">（近期新聞不足，無關鍵字）</p>;
  }
  const max = Math.max(...shown.map((k) => k.score));
  const min = Math.min(...shown.map((k) => k.score));
  const norm = (s: number) => (max === min ? 1 : (s - min) / (max - min));

  return (
    <div className="flex flex-wrap items-center gap-2">
      {shown.map((k) => {
        const t = norm(k.score);
        return (
          <span
            key={k.word}
            className="rounded-lg px-2 py-0.5 font-medium transition-transform hover:scale-105"
            style={{
              fontSize: `${(0.78 + t * 0.85).toFixed(2)}rem`,
              color: "var(--accent)",
              background: "var(--accent-soft)",
              opacity: 0.6 + 0.4 * t,
            }}
            title={`TF-IDF 分數 ${k.score.toFixed(3)}`}
          >
            {k.word}
          </span>
        );
      })}
    </div>
  );
}
