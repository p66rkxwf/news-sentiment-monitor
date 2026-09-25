/**
 * 共用動態參數：全站只用這幾組，節奏才一致。
 * 位移一律用 transform／opacity（GPU 合成），不動 left／width 這類會觸發重排的屬性。
 * 分工：大量元素的進場用 CSS keyframes（globals.css 的 animate-*，搭配下面的 delay()）；
 * Motion 只用在需要彈簧或版面動畫的少數元素（分頁指示器、刻度標記、新聞篩選重排）。
 */

import type { CSSProperties } from "react";

export const EASE_OUT = [0.22, 1, 0.36, 1] as const;

/** 點擊、切換指示器：快而不彈跳過頭 */
export const snappy = { type: "spring", stiffness: 520, damping: 38, mass: 0.7 } as const;

/** 數值標記、長條：稍慢、帶一點慣性 */
export const soft = { type: "spring", stiffness: 180, damping: 26, mass: 0.9 } as const;

/** 進場：淡入＋微幅上移 */
export const enter = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.32, ease: EASE_OUT },
} as const;

/** 列表逐項進場，前 8 項錯開、之後同時出現（長列表不拖泥帶水） */
export function stagger(i: number, base = 0) {
  return { duration: 0.3, ease: EASE_OUT, delay: base + Math.min(i, 8) * 0.035 };
}

/** 按下的回饋 */
export const press = { scale: 0.97 } as const;

/** CSS keyframe 進場（animate-rise／grow-x／grow-y）的逐項延遲；前 8 項錯開 */
export function delay(i: number, baseMs = 0, stepMs = 35): CSSProperties {
  return { animationDelay: `${baseMs + Math.min(i, 8) * stepMs}ms` };
}
