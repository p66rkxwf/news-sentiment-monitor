import { ImageResponse } from "next/og";
import { BrandMark } from "@/lib/brand-mark";

// iOS「加入主畫面」用的圖示（apple-icon 只能是 png/jpg）
export const size = { width: 180, height: 180 };
export const contentType = "image/png";
// 靜態輸出（Cloudflare Pages）時於 build 產生；圖示不依賴請求內容
export const dynamic = "force-static";

export default function AppleIcon() {
  return new ImageResponse(<BrandMark size={180} inset={0.16} />, size);
}
