import { ImageResponse } from "next/og";
import { BrandMark } from "@/lib/brand-mark";

// iOS「加入主畫面」用的圖示（apple-icon 只能是 png/jpg）
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon() {
  return new ImageResponse(<BrandMark size={180} inset={0.16} />, size);
}
