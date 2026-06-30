"use client";

import { useEffect, useState } from "react";

// Client-side user settings, persisted in localStorage. Each change fires a
// window event so any `useSetting` subscriber updates immediately (localStorage
// changes don't fire the native `storage` event in the same tab).
const EVT = "app:settings-changed";

export function readSetting(key: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  return localStorage.getItem(key) ?? fallback;
}

export function writeSetting(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
    window.dispatchEvent(new Event(EVT));
  } catch {
    /* private mode / quota — ignore */
  }
}

/** Reactive read of a setting; re-renders when it changes anywhere in the tab. */
export function useSetting(key: string, fallback: string): string {
  const [value, setValue] = useState(fallback);
  useEffect(() => {
    const read = () => setValue(localStorage.getItem(key) ?? fallback);
    read();
    window.addEventListener(EVT, read);
    return () => window.removeEventListener(EVT, read);
  }, [key, fallback]);
  return value;
}

// --- Indices feed mode -----------------------------------------------------
// Whether index tiles/charts show 24h futures, the cash index, or auto-switch.
export type IndicesMode = "futures" | "cash" | "auto";

export function getIndicesMode(): IndicesMode {
  return readSetting("indicesMode", "futures") as IndicesMode;
}

// --- Live refresh rate -----------------------------------------------------
// Maps a tier to polling intervals (ms) for live prices and the overview.
export const REFRESH_TIERS: Record<string, { price: number; overview: number }> = {
  live: { price: 3000, overview: 10000 },
  normal: { price: 8000, overview: 20000 },
  slow: { price: 20000, overview: 45000 },
};

export function useRefresh(): { price: number; overview: number } {
  const rate = useSetting("refreshRate", "live");
  return REFRESH_TIERS[rate] ?? REFRESH_TIERS.live;
}

// --- Assistant (chat) settings ---------------------------------------------
export function getChatSettings(): { webSearch: boolean; model: string } {
  return {
    webSearch: readSetting("chatWebSearch", "on") !== "off",
    model: readSetting("chatModel", "fast"), // "fast" | "deep"
  };
}
