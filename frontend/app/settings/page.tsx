"use client";

/** 設定：外觀、模型資訊、研究說明（含未複製的確認實驗與預警回測結論）、免責聲明。iOS 式分組卡片。 */

import { BadgeCheck, CalendarDays, Cpu, FlaskConical, GraduationCap, Palette, Scale, ShieldAlert, Target } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useEffect } from "react";
import Skeleton from "@/components/Skeleton";
import ThemeToggle from "@/components/ThemeToggle";
import { PageTitle, TopBar } from "@/components/TopBar";
import { useAppState } from "@/lib/app-state";

function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-2 px-4 text-meta text-ink-3">{title}</h2>
      <div className="card divide-y divide-hairline overflow-hidden">{children}</div>
    </section>
  );
}

function Row({ icon: Icon, tint, label, children }: { icon: LucideIcon; tint: string; label: string; children?: React.ReactNode }) {
  return (
    <div className="flex min-h-14 items-center gap-3 px-4 py-2.5">
      <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${tint}`}>
        <Icon size={16} />
      </span>
      <span className="flex-1 whitespace-nowrap text-body text-ink">{label}</span>
      <span className="min-w-0 break-all text-right">{children}</span>
    </div>
  );
}

function Note({ icon: Icon, tint, children }: { icon: LucideIcon; tint: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-3 px-4 py-3.5">
      <span className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${tint}`}>
        <Icon size={16} />
      </span>
      <p className="flex-1 text-body text-ink-2">{children}</p>
    </div>
  );
}

export default function SettingsPage() {
  const { modelInfo, ensureModelInfo } = useAppState();

  useEffect(() => ensureModelInfo(), [ensureModelInfo]);

  const value = (v: React.ReactNode) => <span className="font-mono text-body tabular-nums text-ink-2">{v}</span>;

  return (
    <>
      <TopBar title={<PageTitle>設定</PageTitle>} />
      <main className="mx-auto w-full max-w-3xl space-y-6 px-4 pt-4 lg:px-8 lg:pt-6">
        <Group title="外觀">
          <Row icon={Palette} tint="bg-brand-soft text-brand" label="主題">
            <ThemeToggle />
          </Row>
        </Group>

        <Group title="情緒模型">
          {modelInfo === null ? (
            <div className="space-y-3 p-4">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : modelInfo === "error" ? (
            <Note icon={ShieldAlert} tint="bg-neg-soft text-neg">
              讀不到模型資訊：後端沒有回應，確認 API 已在 :8001 啟動。
            </Note>
          ) : modelInfo.is_mock ? (
            <Note icon={FlaskConical} tint="bg-warn-soft text-warn">
              模型尚未載入，各頁顯示的是示意資料。
            </Note>
          ) : (
            <>
              <Row icon={Cpu} tint="bg-brand-soft text-brand" label="模型版本">
                {value(modelInfo.model_version)}
              </Row>
              <Row icon={BadgeCheck} tint="bg-pos-soft text-pos" label="測試集 Macro F1">
                {value(modelInfo.test_macro_f1?.toFixed(4) ?? "—")}
              </Row>
              <Row icon={CalendarDays} tint="bg-surface-3 text-ink-2" label="訓練日期">
                {value(modelInfo.trained_at?.slice(0, 10) ?? "—")}
              </Row>
            </>
          )}
        </Group>

        <Group title="研究說明">
          <Note icon={Target} tint="bg-brand-soft text-brand">
            模型判斷的是「這則標題對這支股票是好消息還是壞消息」，不是句子本身的語氣。
          </Note>
          <Note icon={FlaskConical} tint="bg-warn-soft text-warn">
            改用這個模型時量到的人工一致率提升（46.7% → 61.7%），在 2026-09-03 事先聲明的確認實驗中沒有重現（p = 0.804），所以不宣稱模型變得更準。
          </Note>
          <Note icon={ShieldAlert} tint="bg-neg-soft text-neg">
            台股預警在歷史回測中，事前示警率與隨機響鈴無法區分（p = 0.983），只能當作開盤前的即時示警，不是提前預警。
          </Note>
          <p className="px-4 py-3 text-meta text-ink-3">完整紀錄在專案的 docs/ 資料夾（confirmation_2026-09-03.md、alert_backtest.md）。</p>
        </Group>

        <Group title="關於">
          <Note icon={Scale} tint="bg-surface-3 text-ink-2">
            情緒指數是機器學習模型的統計輸出，僅供學術研究與參考，不構成任何投資建議。
          </Note>
          <Note icon={GraduationCap} tint="bg-surface-3 text-ink-2">
            彰師大 115 年百萬專題探索：基於自然語言處理之新聞情緒分析與即時監控系統
          </Note>
        </Group>
      </main>
    </>
  );
}
