/**
 * 內嵌 SVG 圖示組（24 格、描邊 currentColor）。沿用專案既有做法，不引入圖示套件。
 * 一律 aria-hidden：圖示旁都有文字或 aria-label。
 */

type IconProps = { size?: number; className?: string };

function Svg({ size = 22, className, children }: IconProps & { children: React.ReactNode }) {
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
      {children}
    </svg>
  );
}

/** 品牌標記：刻度尺上的一個標記——與總覽的新聞刻度帶同一個概念 */
export function MarkIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M3 17h18" />
      <path d="M6 17v-2M10 17v-2M14 17v-2M18 17v-2" />
      <path d="M15 6v8" strokeWidth="2.6" />
    </Svg>
  );
}

export function OverviewIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M3 16h18" />
      <path d="M6 16v-2M10 16v-2M18 16v-2" />
      <path d="M14 7v9" strokeWidth="2.4" />
    </Svg>
  );
}

export function NewsIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M4 6h16M4 12h16M4 18h10" />
    </Svg>
  );
}

export function WatchlistIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M12 4v16" />
      <path d="M12 7h6M6 12h6M12 17h4" />
    </Svg>
  );
}

export function AlertIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" />
      <path d="M10 20.5a2.2 2.2 0 0 0 4 0" />
    </Svg>
  );
}

export function SettingsIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </Svg>
  );
}

export function SearchIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="M20 20l-4.2-4.2" />
    </Svg>
  );
}

export function RefreshIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M19.5 12a7.5 7.5 0 1 1-2.2-5.3" />
      <path d="M19.5 4.5v4h-4" />
    </Svg>
  );
}

export function ChevronDownIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M7 10l5 5 5-5" />
    </Svg>
  );
}

export function ChevronLeftIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M15 6l-6 6 6 6" />
    </Svg>
  );
}

export function ChevronRightIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M9 6l6 6-6 6" />
    </Svg>
  );
}

export function CloseIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  );
}

export function ExternalIcon(p: IconProps) {
  return (
    <Svg {...p}>
      <path d="M14 5h5v5M19 5l-8 8" />
      <path d="M17 14v4a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1h4" />
    </Svg>
  );
}
