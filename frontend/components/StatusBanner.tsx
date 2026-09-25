/**
 * 資料狀態提示：錯誤（附重試）、stale（新聞源失效改用快取）、mock（模型未載入）。
 * 文案說清楚發生什麼、使用者能做什麼；錯誤訊息的 404/503/429 對應在 app-state.describeError。
 */

import { PAGE_WIDTH, type PageWidth } from "@/components/TopBar";

export default function StatusBanner({
  error,
  stale,
  mock,
  onRetry,
  width = "narrow",
}: {
  error?: string | null;
  stale?: boolean;
  mock?: boolean;
  onRetry?: () => void;
  width?: PageWidth;
}) {
  if (!error && !stale && !mock) return null;
  return (
    <div className={`mx-auto w-full space-y-2 px-4 pt-4 lg:px-8 ${PAGE_WIDTH[width]}`}>
      {error && (
        <div role="alert" className="flex items-center justify-between gap-3 rounded-md bg-neg-soft py-1 pl-4 pr-1 text-body text-neg">
          <span className="py-2">{error}</span>
          {onRetry && (
            <button type="button" onClick={onRetry} className="min-h-11 shrink-0 rounded-md px-3 font-semibold hover:bg-neg-soft">
              重試
            </button>
          )}
        </div>
      )}
      {stale && (
        <p className="rounded-md bg-warn-soft px-4 py-2 text-meta text-warn">
          新聞來源暫時失效，目前顯示的是快取的舊資料。
        </p>
      )}
      {mock && (
        <p className="rounded-md bg-accent-soft px-4 py-2 text-meta text-accent">模型尚未載入，目前顯示的是示意資料。</p>
      )}
    </div>
  );
}
