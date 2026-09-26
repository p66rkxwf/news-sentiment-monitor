import { ImageResponse } from "next/og";
import { BrandMark } from "@/lib/brand-mark";

// 瀏覽器分頁圖示；取代 create-next-app 預設的 favicon.ico
export const size = { width: 32, height: 32 };
export const contentType = "image/png";
// 靜態輸出（Cloudflare Pages）時於 build 產生；圖示不依賴請求內容
export const dynamic = "force-static";

export default function Icon() {
  return new ImageResponse(<BrandMark size={32} inset={0.1} />, size);
}
