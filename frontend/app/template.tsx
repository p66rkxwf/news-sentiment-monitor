/**
 * 每次切換分頁都會重新掛載 template：新頁面淡入＋微幅上移，取代原本的瞬間抽換。
 * 用 CSS keyframe（animate-rise），由合成執行緒執行；新頁面掛載時主執行緒再忙也不影響過場。
 * 只做進場（App Router 沒有可靠的離場時機）。
 */

export default function Template({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-1 animate-rise flex-col">{children}</div>;
}
