/**
 * 新聞列表：情緒標籤色塊 + 信心分數 + 連結原文（新分頁開啟）。
 */

import type { NewsItem, SentimentLabel } from "@/lib/api";

const BADGE: Record<SentimentLabel, { text: string; cls: string }> = {
  positive: {
    text: "正面",
    cls: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300",
  },
  neutral: {
    text: "中性",
    cls: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300",
  },
  negative: {
    text: "負面",
    cls: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300",
  },
};

export default function NewsList({ articles }: { articles: NewsItem[] }) {
  if (articles.length === 0) {
    return <p className="text-sm text-gray-400">目前沒有新聞。</p>;
  }
  return (
    <ul className="divide-y divide-gray-100 dark:divide-gray-800">
      {articles.map((a, i) => {
        const badge = BADGE[a.sentiment];
        return (
          <li key={`${a.url}-${i}`} className="flex items-start gap-3 py-3">
            <span
              className={`mt-0.5 shrink-0 rounded-md px-2 py-0.5 text-xs font-medium ${badge.cls}`}
              title={`信心 ${(a.confidence * 100).toFixed(0)}%`}
            >
              {badge.text} {(a.confidence * 100).toFixed(0)}%
            </span>
            <div className="min-w-0">
              <a
                href={a.url || undefined}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium hover:text-blue-600 hover:underline dark:hover:text-blue-400"
              >
                {a.title}
              </a>
              <div className="mt-0.5 text-xs text-gray-400">{a.published_at.slice(0, 16).replace("T", " ")}</div>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
