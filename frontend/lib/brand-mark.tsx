// App 圖示的共用圖形（給 next/og 的 ImageResponse 用，只能用 flex 與絕對定位）：
// 夜盤藍底上一條刻度尺、一根鋼藍標記——與總覽的新聞刻度帶同一個意象。不含文字，避免 CJK 字型撐大體積。

const BG = "#0d1520";
const RULE = "#7a8ca3";
const MARK = "#5aa9e6";

/** inset：內容離邊的比例；maskable 圖示需要較大的安全邊界（外圈可能被系統裁成圓形） */
export function BrandMark({ size, inset = 0.2 }: { size: number; inset?: number }) {
  const u = (f: number) => Math.max(1, Math.round(size * f));
  const span = 1 - inset * 2;
  const x = (f: number) => u(inset + span * f);
  // 標記頂端到基線底部整組垂直置中；標記略穿過基線，與總覽刻度帶的畫法一致
  const baseTop = inset + span * 0.8;

  return (
    <div style={{ width: size, height: size, display: "flex", position: "relative", background: BG }}>
      <div
        style={{
          position: "absolute",
          left: x(0),
          width: u(span),
          top: u(baseTop),
          height: u(0.035),
          background: RULE,
          borderRadius: u(0.02),
        }}
      />
      {[0.08, 0.3, 0.52, 0.92].map((f) => (
        <div
          key={f}
          style={{
            position: "absolute",
            left: x(f),
            width: u(0.035),
            top: u(baseTop - span * 0.12),
            height: u(span * 0.12),
            background: RULE,
          }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          left: x(0.7),
          width: u(0.085),
          top: u(inset + span * 0.13),
          height: u(span * 0.74),
          background: MARK,
          borderRadius: u(0.045),
        }}
      />
    </div>
  );
}
