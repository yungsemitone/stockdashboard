"use client";

import { useEffect, useRef, useState } from "react";
import { api, clearToken, getUser, type User } from "@/lib/api";
import { readSetting, writeSetting } from "@/lib/settings";

type Theme = "dark" | "light" | "auto";

type Opt = { value: string; label: string };

/** A compact segmented control (the same look as the theme toggle). */
function Segmented({
  options,
  value,
  onChange,
}: {
  options: Opt[];
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="inline-flex w-full rounded-lg border border-neutral-800 bg-neutral-950 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={`flex-1 rounded-md px-2 py-1.5 text-xs transition ${
            value === o.value
              ? "bg-neutral-700 text-white"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="mb-4 last:mb-0">
      <div className="mb-1.5 text-xs font-semibold text-neutral-400">{title}</div>
      {children}
      {hint && <p className="mt-1.5 text-[11px] leading-snug text-neutral-600">{hint}</p>}
    </div>
  );
}

export default function SettingsMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Theme lives in a cookie (read by the server for no-flash SSR); the rest are
  // localStorage settings read through the settings module.
  const [theme, setTheme] = useState<Theme>("dark");
  const [account, setAccount] = useState<User | null>(null);
  const [indices, setIndices] = useState("futures");
  const [refresh, setRefresh] = useState("live");
  const [webSearch, setWebSearch] = useState(true);
  const [model, setModel] = useState("fast");
  const [cleared, setCleared] = useState(false);

  useEffect(() => {
    setAccount(getUser());
    const cl = document.documentElement.classList;
    setTheme(cl.contains("theme-light") ? "light" : cl.contains("theme-auto") ? "auto" : "dark");
    setIndices(readSetting("indicesMode", "futures"));
    setRefresh(readSetting("refreshRate", "live"));
    setWebSearch(readSetting("chatWebSearch", "on") !== "off");
    setModel(readSetting("chatModel", "fast"));
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const applyTheme = (t: Theme) => {
    setTheme(t);
    document.cookie = `theme=${t}; path=/; max-age=31536000; SameSite=Lax`;
    document.documentElement.classList.toggle("theme-light", t === "light");
    document.documentElement.classList.toggle("theme-auto", t === "auto");
  };

  const applyIndices = (v: string) => {
    setIndices(v);
    writeSetting("indicesMode", v);
  };
  const applyRefresh = (v: string) => {
    setRefresh(v);
    writeSetting("refreshRate", v);
  };
  const applyWebSearch = (on: boolean) => {
    setWebSearch(on);
    writeSetting("chatWebSearch", on ? "on" : "off");
  };
  const applyModel = (v: string) => {
    setModel(v);
    writeSetting("chatModel", v);
  };
  const clearChat = () => {
    window.dispatchEvent(new Event("chat:clear"));
    setCleared(true);
    setTimeout(() => setCleared(false), 1500);
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Settings"
        className="flex h-9 w-9 items-center justify-center rounded-lg text-neutral-400 hover:text-neutral-100 hover:bg-neutral-800/60 transition"
      >
        <svg
          width="18"
          height="18"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 max-h-[80vh] w-72 overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-900 p-3 shadow-2xl">
          {account && (
            <Section title="Account">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="truncate text-sm text-neutral-200">
                    {account.username}
                  </div>
                  <div className="truncate text-[11px] text-neutral-500">
                    {account.email}
                  </div>
                </div>
                <button
                  onClick={async () => {
                    try {
                      await api.authLogout();
                    } catch {
                      /* signing out locally regardless */
                    }
                    clearToken();
                    window.location.reload();
                  }}
                  className="shrink-0 rounded-md border border-neutral-700 px-2.5 py-1 text-xs text-neutral-300 transition hover:border-neutral-500"
                >
                  Sign out
                </button>
              </div>
            </Section>
          )}

          <Section
            title="Appearance"
            hint={theme === "auto" ? "Follows your device's light/dark setting." : undefined}
          >
            <Segmented
              options={[
                { value: "dark", label: "Dark" },
                { value: "light", label: "Light" },
                { value: "auto", label: "Auto" },
              ]}
              value={theme}
              onChange={(v) => applyTheme(v as Theme)}
            />
          </Section>

          <Section
            title="Indices feed"
            hint={
              indices === "cash"
                ? "Cash index — matches the value on investing.com / Google."
                : indices === "auto"
                ? "Cash while US markets are open, futures after the close."
                : "E-mini futures — moves live 24h, including overnight & weekends."
            }
          >
            <Segmented
              options={[
                { value: "futures", label: "Futures" },
                { value: "cash", label: "Cash" },
                { value: "auto", label: "Auto" },
              ]}
              value={indices}
              onChange={applyIndices}
            />
          </Section>

          <Section
            title="Refresh rate"
            hint={
              refresh === "slow"
                ? "Slower polling — lighter on data/battery."
                : refresh === "normal"
                ? "Balanced live updates."
                : "Snappiest live ticking."
            }
          >
            <Segmented
              options={[
                { value: "live", label: "Live" },
                { value: "normal", label: "Normal" },
                { value: "slow", label: "Slow" },
              ]}
              value={refresh}
              onChange={applyRefresh}
            />
          </Section>

          <Section title="Assistant">
            <div className="flex items-center justify-between">
              <span className="text-sm text-neutral-300">Web search</span>
              <button
                role="switch"
                aria-checked={webSearch}
                onClick={() => applyWebSearch(!webSearch)}
                className={`relative h-5 w-9 rounded-full transition ${
                  webSearch ? "bg-emerald-600" : "bg-neutral-700"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
                    webSearch ? "left-[18px]" : "left-0.5"
                  }`}
                />
              </button>
            </div>
            <div className="mt-2.5 mb-1 text-[11px] text-neutral-500">Model</div>
            <Segmented
              options={[
                { value: "fast", label: "Fast" },
                { value: "deep", label: "Deep" },
              ]}
              value={model}
              onChange={applyModel}
            />
            <p className="mt-1.5 text-[11px] leading-snug text-neutral-600">
              Fast is the everyday model; Deep is stronger but slower.
            </p>
            <button
              onClick={clearChat}
              className="mt-2.5 w-full rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 hover:text-neutral-200 hover:border-neutral-700 transition"
            >
              {cleared ? "Chat history cleared" : "Clear chat history"}
            </button>
          </Section>
        </div>
      )}
    </div>
  );
}
