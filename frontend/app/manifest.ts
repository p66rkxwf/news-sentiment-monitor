import type { MetadataRoute } from "next";
import { THEME_BACKGROUND } from "@/lib/theme-constants";

// 加到主畫面後以全螢幕（無網址列）開啟；不含 service worker，也不做離線快取
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "財經新聞情緒監控",
    short_name: "新聞情緒",
    description: "美股財經新聞情緒指數與台股情緒預警（彰師大 115 年百萬專題探索）",
    lang: "zh-Hant",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: THEME_BACKGROUND.dark,
    theme_color: THEME_BACKGROUND.dark,
    icons: [
      { src: "/icons/192", sizes: "192x192", type: "image/png" },
      { src: "/icons/512", sizes: "512x512", type: "image/png" },
      { src: "/icons/maskable", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}
