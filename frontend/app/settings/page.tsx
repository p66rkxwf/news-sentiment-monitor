"use client";

/** 設定：外觀、模型資訊、研究說明（含未複製的確認實驗與預警回測結論）、免責聲明。 */

import { useEffect } from "react";
import Section from "@/components/Section";
import Skeleton from "@/components/Skeleton";
import ThemeToggle from "@/components/ThemeToggle";
import { PageTitle, TopBar } from "@/components/TopBar";
import { useAppState } from "@/lib/app-state";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-11 items-center justify-between gap-4 border-b border-border py-2 last:border-b-0">
      <dt className="text-body text-ink-2">{label}</dt>
      <dd className="text-right font-mono text-body tabular-nums text-ink">{children}</dd>
    </div>
  );
}

export default function SettingsPage() {
  const { modelInfo, ensureModelInfo } = useAppState();

  useEffect(() => ensureModelInfo(), [ensureModelInfo]);

  return (
    <>
      <TopBar title={<PageTitle>設定</PageTitle>} />
      <main className="mx-auto w-full max-w-3xl lg:px-8">
        <Section title="外觀">
          <ThemeToggle />
        </Section>

        <Section title="情緒模型">
          {modelInfo === null ? (
            <Skeleton className="h-24 w-full" />
          ) : modelInfo === "error" ? (
            <p className="text-body text-ink-3">讀不到模型資訊：後端沒有回應，確認 API 已在 :8001 啟動。</p>
          ) : modelInfo.is_mock ? (
            <p className="text-body text-ink-3">模型尚未載入，各頁顯示的是示意資料。</p>
          ) : (
            <dl>
              <Row label="模型版本">{modelInfo.model_version}</Row>
              <Row label="測試集 Macro F1">{modelInfo.test_macro_f1?.toFixed(4) ?? "—"}</Row>
              <Row label="訓練日期">{modelInfo.trained_at?.slice(0, 10) ?? "—"}</Row>
            </dl>
          )}
        </Section>

        <Section title="研究說明">
          <div className="max-w-prose space-y-3 text-body text-ink-2">
            <p>
              模型判斷的是「這則標題對這支股票是好消息還是壞消息」，不是句子本身的語氣。
            </p>
            <p>
              改用這個模型時量到的人工一致率提升（46.7% → 61.7%），在 2026-09-03 事先聲明的確認實驗中沒有重現（p = 0.804），所以不宣稱模型變得更準。
            </p>
            <p>
              台股預警在歷史回測中，事前示警率與隨機響鈴無法區分（p = 0.983），只能當作開盤前的即時示警，不是提前預警。
            </p>
            <p className="text-meta text-ink-3">完整紀錄在專案的 docs/ 資料夾（confirmation_2026-09-03.md、alert_backtest.md）。</p>
          </div>
        </Section>

        <Section title="關於" className="border-b-0">
          <div className="max-w-prose space-y-3 text-body text-ink-2">
            <p>情緒指數是機器學習模型的統計輸出，僅供學術研究與參考，不構成任何投資建議。</p>
            <p className="text-meta text-ink-3">彰師大 115 年百萬專題探索：基於自然語言處理之新聞情緒分析與即時監控系統</p>
          </div>
        </Section>
      </main>
    </>
  );
}
