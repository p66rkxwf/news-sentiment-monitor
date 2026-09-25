/**
 * 品牌標記：刻度尺上的一個標記——與總覽的新聞刻度帶同一個意象（App 圖示見 lib/brand-mark.tsx）。
 * 其餘介面圖示一律用 lucide-react。
 */

export function MarkIcon({ size = 22, className }: { size?: number; className?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      <path d="M3 17h18" />
      <path d="M6 17v-2M10 17v-2M14 17v-2M18 17v-2" />
      <path d="M15 6v8" strokeWidth="2.6" />
    </svg>
  );
}
