"use client";

/**
 * 資料狀態提示：錯誤（附重試）、stale（新聞源失效改用快取）、mock（模型未載入）。
 * 文案說清楚發生什麼、使用者能做什麼；錯誤訊息的 404/503/429 對應在 app-state.describeError。
 */

import { CircleAlert, DatabaseBackup, FlaskConical, RotateCw } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { PAGE_WIDTH, type PageWidth } from "@/components/TopBar";
import { EASE_OUT, press } from "@/lib/motion";

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
  return (
    <AnimatePresence initial={false}>
      {(error || stale || mock) && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -6 }}
          transition={{ duration: 0.22, ease: EASE_OUT }}
          className={`mx-auto w-full space-y-2 px-4 pt-4 lg:px-8 ${PAGE_WIDTH[width]}`}
        >
          {error && (
            <div role="alert" className="flex items-center gap-3 rounded-2xl border border-neg/30 bg-neg-soft py-2 pl-4 pr-2 text-body text-neg">
              <CircleAlert size={18} className="shrink-0" />
              <span className="flex-1 py-1">{error}</span>
              {onRetry && (
                <motion.button
                  type="button"
                  whileTap={press}
                  onClick={onRetry}
                  className="flex min-h-10 shrink-0 items-center gap-1.5 rounded-full bg-neg px-4 text-meta font-semibold text-white"
                >
                  <RotateCw size={14} /> 重試
                </motion.button>
              )}
            </div>
          )}
          {stale && (
            <p className="flex items-center gap-2 rounded-2xl bg-warn-soft px-4 py-2.5 text-meta text-warn">
              <DatabaseBackup size={15} className="shrink-0" />
              新聞來源暫時失效，目前顯示的是快取的舊資料。
            </p>
          )}
          {mock && (
            <p className="flex items-center gap-2 rounded-2xl bg-brand-soft px-4 py-2.5 text-meta text-brand">
              <FlaskConical size={15} className="shrink-0" />
              模型尚未載入，目前顯示的是示意資料。
            </p>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
