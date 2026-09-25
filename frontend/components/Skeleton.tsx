/** 載入中的占位塊：形狀貼近真實內容，資料到了不會跳版；減少動態偏好下不閃爍（globals.css） */
export default function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded bg-surface-2 ${className}`} />;
}
