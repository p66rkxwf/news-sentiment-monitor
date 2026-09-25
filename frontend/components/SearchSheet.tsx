"use client";

/**
 * 切換標的：手機是可往下拖曳關閉的底部抽屜（vaul），桌機是置中對話框（Radix Dialog）。
 * 格式與後端 deps.py 同一條正規，錯誤格式在前端就擋下（少一次 422）。
 * 不給空白畫面：列出輸入中的代號、最近查詢與追蹤清單，點一下就切換。
 */

import { ArrowUpRight, Clock, Search, Star } from "lucide-react";
import { motion } from "motion/react";
import { useRef, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Drawer, DrawerContent, DrawerDescription, DrawerTitle } from "@/components/ui/drawer";
import { useIsDesktop } from "@/hooks/use-media-query";
import { TICKER_PATTERN } from "@/lib/api";
import { useAppState, WATCHLIST } from "@/lib/app-state";
import { delay, press } from "@/lib/motion";

function SearchBody({
  onDone,
  autoFocus,
  inputRef,
}: {
  onDone: () => void;
  autoFocus: boolean;
  inputRef?: React.Ref<HTMLInputElement>;
}) {
  const { ticker, selectTicker, recent } = useAppState();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);

  const typed = value.trim().toUpperCase();
  const typedValid = TICKER_PATTERN.test(typed);

  const choose = (t: string) => {
    selectTicker(t);
    onDone();
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!typed) return;
    if (!typedValid) {
      setInvalid(true);
      return;
    }
    choose(typed);
  };

  const others = WATCHLIST.filter((t) => !recent.includes(t));

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <form onSubmit={submit} className="px-4 pb-3">
        <div
          className={`flex items-center gap-3 rounded-2xl border bg-surface-2 px-4 transition-colors focus-within:border-brand ${
            invalid ? "border-neg" : "border-transparent"
          }`}
        >
          <Search size={18} className="shrink-0 text-ink-3" />
          <input
            ref={inputRef}
            autoFocus={autoFocus}
            type="text"
            inputMode="text"
            autoCapitalize="characters"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            enterKeyHint="search"
            aria-label="美股代號"
            aria-invalid={invalid}
            placeholder="輸入美股代號，例如 AAPL"
            value={value}
            onChange={(e) => {
              setValue(e.target.value);
              setInvalid(false);
            }}
            className="min-h-12 min-w-0 flex-1 bg-transparent font-mono text-body uppercase text-ink outline-none focus-visible:outline-none placeholder:font-sans placeholder:normal-case placeholder:text-ink-3"
          />
        </div>
        {invalid && (
          <p role="alert" className="mt-2 px-1 text-meta text-neg">
            代號格式不對：1–5 個英文字母，可加一碼類別（例如 AAPL、BRK.B）。
          </p>
        )}
      </form>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 pb-6">
        {typed && typedValid && (
          <motion.button
            type="button"
            whileTap={press}
            onClick={() => choose(typed)}
            className="mb-4 flex min-h-14 w-full animate-rise items-center gap-3 rounded-2xl bg-brand-soft px-4 text-left"
          >
            <Search size={18} className="text-brand" />
            <span className="flex-1 text-body text-ink-2">
              查詢 <span className="font-mono font-semibold text-ink">{typed}</span>
            </span>
            <ArrowUpRight size={18} className="text-brand" />
          </motion.button>
        )}

        {recent.length > 0 && (
          <section className="mb-5">
            <h2 className="mb-2 flex items-center gap-1.5 px-1 text-meta text-ink-3">
              <Clock size={13} /> 最近查詢
            </h2>
            <div className="flex flex-wrap gap-2">
              {recent.map((t, i) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => choose(t)}
                  style={delay(i, 120)}
                  className={`min-h-10 animate-rise rounded-full border px-4 font-mono text-body font-semibold transition-[scale] duration-150 active:scale-95 ${
                    t === ticker ? "border-brand bg-brand-soft text-brand" : "border-hairline bg-surface-2 text-ink"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          </section>
        )}

        {others.length > 0 && (
          <section>
            <h2 className="mb-2 flex items-center gap-1.5 px-1 text-meta text-ink-3">
              <Star size={13} /> 追蹤清單
            </h2>
            <ul className="overflow-hidden rounded-2xl border border-hairline bg-surface-2">
              {others.map((t, i) => (
                <li key={t} style={delay(i, 160)} className="animate-rise border-b border-hairline last:border-b-0">
                  <button
                    type="button"
                    onClick={() => choose(t)}
                    className="flex min-h-14 w-full items-center gap-3 px-4 text-left transition-colors active:bg-surface-3"
                  >
                    <span className="flex size-9 items-center justify-center rounded-full bg-surface-3 font-mono text-meta font-semibold text-ink-2">
                      {t.slice(0, 2)}
                    </span>
                    <span className={`flex-1 font-mono text-body font-semibold ${t === ticker ? "text-brand" : "text-ink"}`}>
                      {t}
                    </span>
                    {t === ticker && <span className="text-meta text-ink-3">目前檢視</span>}
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}

export default function SearchSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const isDesktop = useIsDesktop();
  const inputRef = useRef<HTMLInputElement>(null);
  const close = () => onOpenChange(false);

  if (isDesktop) {
    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          showCloseButton={false}
          className="top-24 flex max-h-[70vh] translate-y-0 flex-col gap-0 rounded-3xl border-hairline bg-surface p-0 pt-4 shadow-(--shadow-float) sm:max-w-md"
        >
          <DialogTitle className="sr-only">切換標的</DialogTitle>
          <DialogDescription className="sr-only">輸入美股代號，或從最近查詢與追蹤清單選一檔</DialogDescription>
          <SearchBody onDone={close} autoFocus />
        </DialogContent>
      </Dialog>
    );
  }

  return (
    // 抽屜滑到定位後才聚焦輸入框：同時滑入又彈鍵盤，第一格會卡住（vaul 的建議做法）
    <Drawer open={open} onOpenChange={onOpenChange} onAnimationEnd={(isOpen) => isOpen && inputRef.current?.focus()}>
      <DrawerContent
        onOpenAutoFocus={(e) => e.preventDefault()}
        className="h-[85dvh] max-h-[85dvh] rounded-t-3xl border-hairline bg-surface"
      >
        <DrawerTitle className="px-4 pb-3 pt-3 text-title font-semibold">切換標的</DrawerTitle>
        <DrawerDescription className="sr-only">輸入美股代號，或從最近查詢與追蹤清單選一檔</DrawerDescription>
        {/* 關閉後 Radix 會在離場動畫結束才卸載內容；再次開啟時輸入框是全新的 */}
        <SearchBody onDone={close} autoFocus={false} inputRef={inputRef} />
      </DrawerContent>
    </Drawer>
  );
}
