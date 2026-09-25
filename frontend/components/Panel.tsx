/**
 * 內容卡片：標題列（圖示＋標題＋右側動作）＋內容。取代原本的分隔線區段，給深色底上的層次。
 * 卡片外觀集中在 globals.css 的 `card` utility。
 */

import type { LucideIcon } from "lucide-react";
import { cn } from "cn";

export default function Panel({
  title,
  icon: Icon,
  action,
  children,
  className,
}: {
  title?: string;
  icon?: LucideIcon;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("card p-5", className)}>
      {(title || action) && (
        <div className="mb-4 flex min-h-8 items-center justify-between gap-4">
          {title && (
            <h2 className="flex items-center gap-2 text-body font-semibold text-ink-2">
              {Icon && <Icon size={16} className="text-ink-3" />}
              {title}
            </h2>
          )}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
