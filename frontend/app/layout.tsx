import type { Metadata, Viewport } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import AppShell from "@/components/AppShell";
import { AppStateProvider } from "@/lib/app-state";
import { THEME_BACKGROUND, THEME_BOOT_SCRIPT } from "@/lib/theme-constants";
import "./globals.css";

// IBM Plex：Sans 管介面文字，Mono 只給數字（情緒分數、信心、z 值）；中文走系統字
const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "600"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "600"],
});

export const metadata: Metadata = {
  title: "財經新聞情緒監控",
  description: "基於自然語言處理之新聞情緒分析與即時監控系統（彰師大 115 年百萬專題探索）",
  applicationName: "新聞情緒",
  appleWebApp: { capable: true, title: "新聞情緒", statusBarStyle: "black-translucent" },
  // Next 的 appleWebApp.capable 輸出的是 mobile-web-app-capable；舊版 iOS 只認帶 apple- 前綴的這個
  other: { "apple-mobile-web-app-capable": "yes" },
};

export const viewport: Viewport = {
  themeColor: THEME_BACKGROUND.dark,
  viewportFit: "cover",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="zh-Hant"
      data-theme="dark"
      className={`${plexSans.variable} ${plexMono.variable} antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOT_SCRIPT }} />
      </head>
      <body>
        <AppStateProvider>
          <AppShell>{children}</AppShell>
        </AppStateProvider>
      </body>
    </html>
  );
}
