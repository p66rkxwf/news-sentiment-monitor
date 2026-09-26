import { ImageResponse } from "next/og";
import { BrandMark } from "@/lib/brand-mark";

// manifest 用的安裝圖示。用自訂路由而非 icon.tsx + generateImageMetadata，
// 是因為後者產生的網址格式文件沒寫明，manifest 需要穩定的網址。
// 網址帶 .png：靜態輸出時檔名即網址，靜態主機（Cloudflare Pages）依副檔名給 Content-Type。
const VARIANTS = {
  "192.png": { size: 192, inset: 0.2 },
  "512.png": { size: 512, inset: 0.2 },
  "maskable.png": { size: 512, inset: 0.28 }, // Android 可能裁成圓形，內容留在中央安全區
} as const;

// build 時產生三張圖（靜態輸出只能用不依賴 Request 的 GET）
export const dynamic = "force-static";
export const dynamicParams = false;

type Variant = keyof typeof VARIANTS;

export function generateStaticParams() {
  return Object.keys(VARIANTS).map((variant) => ({ variant }));
}

export async function GET(_req: Request, { params }: { params: Promise<{ variant: string }> }) {
  const { variant } = await params;
  const spec = VARIANTS[variant as Variant];
  if (!spec) return new Response("Not found", { status: 404 });
  return new ImageResponse(<BrandMark size={spec.size} inset={spec.inset} />, {
    width: spec.size,
    height: spec.size,
  });
}
