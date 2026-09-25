import type { NextConfig } from "next";

// 瀏覽器（含手機）只連前端，/api/* 由 Next 轉送給 FastAPI：不必處理後端 CORS，也不必讓後端開在區網上。
// 代價：後端限流以 IP 計，經轉送後所有裝置共用同一份額度（見 README）。
const API_PROXY_TARGET = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8001";

const nextConfig: NextConfig = {
  // 手機用區網 IP 開 dev server 時要列入，例如 DEV_ORIGINS=192.168.1.23（逗號分隔）
  allowedDevOrigins: (process.env.DEV_ORIGINS ?? "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean),
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_PROXY_TARGET}/api/:path*` }];
  },
};

export default nextConfig;
