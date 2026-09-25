import { ImageResponse } from "next/og";
import { BrandMark } from "@/lib/brand-mark";

// 瀏覽器分頁圖示；取代 create-next-app 預設的 favicon.ico
export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(<BrandMark size={32} inset={0.1} />, size);
}
