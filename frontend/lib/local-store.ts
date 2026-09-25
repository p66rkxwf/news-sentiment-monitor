"use client";

import { useSyncExternalStore } from "react";

/**
 * 以 localStorage 為底的小型外部 store（useSyncExternalStore），存「每位使用者自己的偏好」。
 *
 * - 讀寫都包 try/catch：無痕模式或封鎖網站資料時會丟例外，此時改存記憶體，只在本次開啟有效
 * - 伺服器端與 hydration 期間一律回 serverValue，hydration 後才換成實際值——不必在 effect 裡 setState
 * - snapshot 依原始字串快取，未變動時回同一個參考，避免 useSyncExternalStore 無限重繪
 */
export function createLocalStore<T>(key: string, parse: (raw: string | null) => T, serverValue: T) {
  const listeners = new Set<() => void>();
  let memoryOnly = false;
  let memory: string | null = null;
  let cachedRaw: string | null | undefined;
  let cachedValue: T = serverValue;

  const readRaw = (): string | null => {
    if (memoryOnly) return memory;
    try {
      return localStorage.getItem(key);
    } catch {
      memoryOnly = true;
      return memory;
    }
  };

  const get = (): T => {
    const raw = readRaw();
    if (raw !== cachedRaw) {
      cachedRaw = raw;
      cachedValue = parse(raw);
    }
    return cachedValue;
  };

  const subscribe = (onChange: () => void) => {
    listeners.add(onChange);
    const onStorage = (e: StorageEvent) => {
      if (e.key === key) onChange();
    };
    window.addEventListener("storage", onStorage);
    return () => {
      listeners.delete(onChange);
      window.removeEventListener("storage", onStorage);
    };
  };

  const set = (raw: string) => {
    memory = raw;
    if (!memoryOnly) {
      try {
        localStorage.setItem(key, raw);
      } catch {
        memoryOnly = true;
      }
    }
    listeners.forEach((l) => l());
  };

  return {
    get,
    set,
    useValue: (): T => useSyncExternalStore(subscribe, get, () => serverValue),
  };
}
