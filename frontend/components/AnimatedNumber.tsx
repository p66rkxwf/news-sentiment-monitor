"use client";

/**
 * 數字從上一個值滾到新值（motion 的 animate，直接改 textContent，不經 React 重繪）。
 * 在繪製前（layout effect）就設好起點，不會先閃出終值；使用者偏好減少動態時直接顯示終值。
 */

import { animate, useReducedMotion } from "motion/react";
import { useLayoutEffect, useRef } from "react";
import { EASE_OUT } from "@/lib/motion";

export default function AnimatedNumber({
  value,
  format,
  className,
}: {
  value: number;
  format: (v: number) => string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const from = useRef(0);
  const reduced = useReducedMotion();

  useLayoutEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (reduced) {
      node.textContent = format(value);
      from.current = value;
      return;
    }
    const controls = animate(from.current, value, {
      duration: 0.9,
      ease: EASE_OUT,
      onUpdate: (v) => {
        node.textContent = format(v);
      },
    });
    from.current = value;
    return () => controls.stop();
  }, [value, format, reduced]);

  return (
    <span ref={ref} className={className}>
      {format(value)}
    </span>
  );
}
