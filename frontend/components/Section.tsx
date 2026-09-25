/**
 * 頁內分段：整行分隔線切開，不用卡片框。標題是一般句子大小寫、ink-2 色，右側可放一個動作。
 */

export default function Section({
  title,
  action,
  children,
  className = "",
}: {
  title?: string;
  action?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={`border-b border-border px-4 py-6 lg:px-0 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-4">
          {title && <h2 className="text-body font-semibold text-ink-2">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
