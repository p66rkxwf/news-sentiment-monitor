/**
 * 載入中的占位塊：一道流光從左掃到右（只動 transform）。形狀與高度貼近真實內容，資料到了不跳版。
 */

import { cn } from "cn";

export default function Skeleton({ className }: { className?: string }) {
  return (
    <div aria-hidden="true" data-skeleton className={cn("relative overflow-hidden rounded-lg bg-surface-2", className)}>
      <div className="absolute inset-0 animate-shimmer bg-linear-to-r from-transparent via-white/6 to-transparent" />
    </div>
  );
}
