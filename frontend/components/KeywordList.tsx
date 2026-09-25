/**
 * 熱門關鍵字：後端已算好近期標題的 TF-IDF 分數，這裡依分數排行、以長條表示相對強弱。
 * （取代原本的字雲：字級不再承載分數，四階字級不被打破。）
 */

import type { KeywordScore } from "@/lib/api";

const LIMIT = 10;
const MOBILE_LIMIT = 6; // 單欄時只列前 6 名，雙欄（sm 以上）列滿 10 名

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

export default function KeywordList({ keywords, ticker }: { keywords: KeywordScore[]; ticker?: string }) {
  const selfWords = new Set<string>(
    ticker ? [ticker.toLowerCase(), ...(BRAND_ALIASES[ticker.toUpperCase()] ?? [])] : [],
  );
  const filtered = keywords.filter((k) => !selfWords.has(k.word.toLowerCase()));
  // 全被濾掉（極少見）就退回原始清單，避免整塊空白
  const shown = (filtered.length > 0 ? filtered : keywords).slice(0, LIMIT);

  if (shown.length === 0) {
    return <p className="text-body text-ink-3">近期新聞太少，還排不出關鍵字。</p>;
  }
  const max = Math.max(...shown.map((k) => k.score));

  return (
    <ol className="grid gap-x-8 sm:grid-cols-2">
      {shown.map((k, i) => (
        <li
          key={k.word}
          className={`${i >= MOBILE_LIMIT ? "hidden sm:flex" : "flex"} min-h-10 items-center gap-3 border-b border-border`}
          title={`TF-IDF 分數 ${k.score.toFixed(3)}`}
        >
          <span className="w-28 shrink-0 truncate text-body text-ink">{k.word}</span>
          <span className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2">
            <span className="block h-full rounded-full bg-accent" style={{ width: `${max > 0 ? (k.score / max) * 100 : 0}%` }} />
          </span>
        </li>
      ))}
    </ol>
  );
}
