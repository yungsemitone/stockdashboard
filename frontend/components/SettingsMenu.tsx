"use client";

import { useEffect, useRef, useState } from "react";

type Theme = "dark" | "light";

export default function SettingsMenu() {
  const [open, setOpen] = useState(false);
  const [theme, setTheme] = useState<Theme>("dark");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Reflect whatever the server already applied (from the theme cookie).
    setTheme(
      document.documentElement.classList.contains("theme-light") ? "light" : "dark",
    );
  }, []);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const apply = (t: Theme) => {
    setTheme(t);
    // Persist for SSR on the next load, and flip instantly now.
    document.cookie = `theme=${t}; path=/; max-age=31536000; SameSite=Lax`;
    document.documentElement.classList.toggle("theme-light", t === "light");
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
        <div className="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-neutral-800 bg-neutral-900 p-3 shadow-2xl">
          <div className="text-xs font-semibold text-neutral-400 mb-2">
            Appearance
          </div>
          <div className="inline-flex w-full rounded-lg border border-neutral-800 bg-neutral-950 p-0.5">
            {(["dark", "light"] as Theme[]).map((t) => (
              <button
                key={t}
                onClick={() => apply(t)}
                className={`flex-1 rounded-md px-3 py-1.5 text-sm capitalize transition ${
                  theme === t
                    ? "bg-neutral-700 text-white"
                    : "text-neutral-400 hover:text-neutral-200"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
          <p className="mt-2.5 text-[11px] text-neutral-600">
            More settings coming soon.
          </p>
        </div>
      )}
    </div>
  );
}
