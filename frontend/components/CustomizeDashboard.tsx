"use client";

import { useEffect, useRef, useState } from "react";
import {
  api,
  type SearchResult,
  type UniverseClass,
  type UniverseConfig,
  type UniverseSymbol,
} from "@/lib/api";
import { bumpUniverse } from "@/lib/universe";

function Toggle({ on, onChange }: { on: boolean; onChange: () => void }) {
  return (
    <button
      role="switch"
      aria-checked={on}
      onClick={onChange}
      className={`relative h-5 w-9 shrink-0 rounded-full transition ${
        on ? "bg-emerald-600" : "bg-neutral-700"
      }`}
    >
      <span
        className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${
          on ? "left-[18px]" : "left-0.5"
        }`}
      />
    </button>
  );
}

/** Debounced symbol search that adds the picked result to a class. */
function AddSymbol({
  onAdd,
  disabled,
}: {
  onAdd: (s: UniverseSymbol) => void;
  disabled: boolean;
}) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const query = q.trim();
    if (query.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    const id = setTimeout(async () => {
      try {
        const r = await api.search(query);
        setResults(r.results);
        setOpen(true);
      } catch {
        setResults([]);
      }
    }, 200);
    return () => clearTimeout(id);
  }, [q]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const pick = (r: SearchResult) => {
    onAdd({ symbol: r.symbol, name: r.name });
    setQ("");
    setResults([]);
    setOpen(false);
  };

  return (
    <div ref={ref} className="relative">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        placeholder={disabled ? "This section is full" : "Search to add a symbol…"}
        disabled={disabled}
        className="w-full rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-600 outline-none focus:border-neutral-600 disabled:opacity-50"
      />
      {open && (
        <div className="absolute z-50 mt-1 w-full overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900 shadow-xl">
          {results.slice(0, 6).map((r, i) => (
            <button
              key={`${r.symbol}-${i}`}
              onClick={() => pick(r)}
              className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-neutral-800"
            >
              <span className="min-w-0 truncate text-sm text-neutral-100">
                {r.name}
              </span>
              <span className="shrink-0 text-xs text-neutral-500">
                {r.symbol}
                {r.type ? ` · ${r.type}` : ""}
              </span>
            </button>
          ))}
          {results.length === 0 && (
            <div className="px-3 py-2 text-sm text-neutral-500">No matches</div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CustomizeDashboard() {
  const [open, setOpen] = useState(false);
  const [cfg, setCfg] = useState<UniverseConfig | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setErr(null);
    api
      .universeConfig()
      .then(setCfg)
      .catch(() => setErr("Couldn't load the current setup."));
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const save = async (next: UniverseConfig) => {
    setCfg(next); // optimistic — the PUT response then trues it up
    setBusy(true);
    setErr(null);
    try {
      const saved = await api.universeSave(
        next.classes.map(({ key, visible, symbols }) => ({ key, visible, symbols })),
      );
      setCfg(saved);
      bumpUniverse();
    } catch {
      setErr("Couldn't save that change — is the backend reachable?");
      try {
        setCfg(await api.universeConfig());
      } catch {
        /* keep the optimistic state; next change retries */
      }
    } finally {
      setBusy(false);
    }
  };

  const mutateClass = (key: string, fn: (c: UniverseClass) => UniverseClass) => {
    if (!cfg) return;
    save({ ...cfg, classes: cfg.classes.map((c) => (c.key === key ? fn(c) : c)) });
  };

  const reset = async () => {
    setBusy(true);
    setErr(null);
    try {
      const fresh = await api.universeReset();
      setCfg(fresh);
      bumpUniverse();
    } catch {
      setErr("Couldn't reset.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-neutral-800 px-3 py-1.5 text-sm text-neutral-400 hover:text-neutral-200 hover:border-neutral-700 transition"
      >
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="4" y1="21" x2="4" y2="14" />
          <line x1="4" y1="10" x2="4" y2="3" />
          <line x1="12" y1="21" x2="12" y2="12" />
          <line x1="12" y1="8" x2="12" y2="3" />
          <line x1="20" y1="21" x2="20" y2="16" />
          <line x1="20" y1="12" x2="20" y2="3" />
          <line x1="1" y1="14" x2="7" y2="14" />
          <line x1="9" y1="8" x2="15" y2="8" />
          <line x1="17" y1="16" x2="23" y2="16" />
        </svg>
        Customize
      </button>

      {open && (
        <div
          className="fixed inset-0 z-40 flex items-start justify-center overflow-y-auto bg-black/60 p-4 sm:py-10"
          onMouseDown={(e) => e.target === e.currentTarget && setOpen(false)}
        >
          <div className="w-full max-w-2xl rounded-xl border border-neutral-800 bg-neutral-900 shadow-2xl">
            <header className="flex items-center justify-between gap-3 border-b border-neutral-800 px-5 py-3.5">
              <div>
                <h3 className="font-semibold">Customize dashboard</h3>
                <p className="mt-0.5 text-xs text-neutral-500">
                  Pick what each section tracks, or hide sections entirely.
                  Changes apply instantly.
                </p>
              </div>
              <div className="flex items-center gap-3">
                {busy && (
                  <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
                )}
                <button
                  onClick={() => setOpen(false)}
                  aria-label="Close"
                  className="rounded-md px-2 py-1 text-neutral-400 hover:text-neutral-100"
                >
                  ✕
                </button>
              </div>
            </header>

            {err && (
              <p className="border-b border-neutral-800 px-5 py-2.5 text-sm text-rose-400">
                {err}
              </p>
            )}
            {!cfg && !err && (
              <p className="px-5 py-6 text-sm text-neutral-500">Loading…</p>
            )}

            {cfg?.classes.map((c) => (
              <div
                key={c.key}
                className="border-b border-neutral-800/70 px-5 py-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-medium">{c.label}</span>
                    <span className="text-xs text-neutral-600">
                      {c.symbols.length}/{cfg.max_per_class}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-neutral-500">
                      {c.visible ? "Shown" : "Hidden"}
                    </span>
                    <Toggle
                      on={c.visible}
                      onChange={() =>
                        mutateClass(c.key, (x) => ({ ...x, visible: !x.visible }))
                      }
                    />
                  </div>
                </div>

                <div className={c.visible ? "" : "pointer-events-none opacity-40"}>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {c.symbols.map((s) => (
                      <span
                        key={s.symbol}
                        className="inline-flex items-center gap-1 rounded-full border border-neutral-800 bg-neutral-950 py-0.5 pl-2.5 pr-1 text-xs"
                      >
                        <span className="max-w-44 truncate text-neutral-200">
                          {s.name}
                        </span>
                        <span className="text-neutral-500">{s.symbol}</span>
                        <button
                          onClick={() =>
                            mutateClass(c.key, (x) => ({
                              ...x,
                              symbols: x.symbols.filter(
                                (y) => y.symbol !== s.symbol,
                              ),
                            }))
                          }
                          aria-label={`Remove ${s.symbol}`}
                          className="rounded-full px-1 text-neutral-500 transition hover:text-rose-400"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    {c.symbols.length === 0 && (
                      <span className="text-xs text-neutral-600">
                        Nothing here — add instruments below.
                      </span>
                    )}
                  </div>
                  <div className="mt-2.5">
                    <AddSymbol
                      disabled={c.symbols.length >= cfg.max_per_class}
                      onAdd={(s) =>
                        mutateClass(c.key, (x) =>
                          x.symbols.some((y) => y.symbol === s.symbol)
                            ? x
                            : { ...x, symbols: [...x.symbols, s] },
                        )
                      }
                    />
                  </div>
                </div>
              </div>
            ))}

            <footer className="flex items-center justify-between px-5 py-3.5">
              <button
                onClick={reset}
                disabled={!cfg || cfg.is_default || busy}
                className="text-xs text-neutral-500 transition hover:text-neutral-300 disabled:cursor-default disabled:opacity-40"
              >
                Reset to defaults
              </button>
              <button
                onClick={() => setOpen(false)}
                className="rounded-lg bg-neutral-100 px-4 py-1.5 text-sm font-medium text-neutral-900 transition hover:bg-white"
              >
                Done
              </button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
}
