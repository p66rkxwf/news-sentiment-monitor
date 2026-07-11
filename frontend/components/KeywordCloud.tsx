/**
 * 關鍵字雲：後端已算好 TF-IDF 分數，前端只做「分數 → 字級」映射，不引繪圖庫。
 */

import type { KeywordScore } from "@/lib/api";

export default function KeywordCloud({ keywords }: { keywords: KeywordScore[] }) {
  if (keywords.length === 0) {
    return <p className="text-sm text-gray-400">（近期新聞不足，無關鍵字）</p>;
  }
  const max = Math.max(...keywords.map((k) => k.score));
  const min = Math.min(...keywords.map((k) => k.score));
  const size = (score: number) => {
    if (max === min) return 1.1;
    return 0.8 + ((score - min) / (max - min)) * 1.0; // 0.8rem ~ 1.8rem
  };
  return (
    <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      {keywords.map((k) => (
        <span
          key={k.word}
          className="text-blue-700 dark:text-blue-300"
          style={{ fontSize: `${size(k.score).toFixed(2)}rem`, opacity: 0.55 + 0.45 * (max === min ? 1 : (k.score - min) / (max - min)) }}
          title={`分數 ${k.score.toFixed(3)}`}
        >
          {k.word}
        </span>
      ))}
    </div>
  );
}
