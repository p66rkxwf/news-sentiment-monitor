/**
 * 關鍵字雲：後端已算好 TF-IDF 分數，前端只做「分數 → 字級/濃淡」映射，不引繪圖庫。
 */

import type { KeywordScore } from "@/lib/api";

export default function KeywordCloud({ keywords }: { keywords: KeywordScore[] }) {
  if (keywords.length === 0) {
    return <p className="text-sm text-ink-3">（近期新聞不足，無關鍵字）</p>;
  }
  const max = Math.max(...keywords.map((k) => k.score));
  const min = Math.min(...keywords.map((k) => k.score));
  const norm = (s: number) => (max === min ? 1 : (s - min) / (max - min));

  return (
    <div className="flex flex-wrap items-center gap-2">
      {keywords.map((k) => {
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
