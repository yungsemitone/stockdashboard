"use client";

import { useEffect, useRef, useState } from "react";
import {
  api,
  getToken,
  type AlertChannels,
  type AlertEvent,
  type AlertRule,
  type AlertsState,
  type SearchResult,
} from "@/lib/api";

const SEEN_KEY = "alerts-seen-ts";

// One dropdown folds kind + direction into a plain-English condition.
const CONDITIONS = [
  { value: "move:any", label: "moves ±", unit: "%" },
  { value: "move:up", label: "rises +", unit: "%" },
  { value: "move:down", label: "drops −", unit: "%" },
  { value: "above:any", label: "goes above", unit: "$" },
  { value: "below:any", label: "drops below", unit: "$" },
];

function condLabel(r: { kind: string; direction: string; threshold: number }) {
  if (r.kind === "move") {
    const sign = r.direction === "up" ? "+" : r.direction === "down" ? "−" : "±";
    return `moves ${sign}${r.threshold}% in a day`;
  }
  return `${r.kind} ${r.threshold.toLocaleString()}`;
}

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

/** Symbols that report earnings (equities/ETFs — not indices, FX, crypto). */
const reportable = (symbol: string) =>
  !symbol.startsWith("^") &&
  !symbol.includes("=") &&
  !symbol.endsWith("-USD") &&
  symbol !== "DX-Y.NYB";

export default function AlertsBell() {
  const [open, setOpen] = useState(false);
  const [view, setView] = useState<"main" | "rules" | string>("main");
  const [state, setState] = useState<AlertsState | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [toasts, setToasts] = useState<AlertEvent[]>([]);
  const [unread, setUnread] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const lastNotified = useRef<number>(Date.now() / 1000 - 60);

  // --- new-alert form state
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [picked, setPicked] = useState<{ symbol: string; name: string } | null>(null);
  const [cond, setCond] = useState("move:any");
  const [threshold, setThreshold] = useState("");
  const [testMsg, setTestMsg] = useState<Record<string, string>>({});

  const seenTs = () => Number(localStorage.getItem(SEEN_KEY) || 0);
  const markSeen = () => {
    localStorage.setItem(SEEN_KEY, String(Date.now() / 1000));
    setUnread(false);
  };

  // Poll for the signed-in account's trigger events (the bell lives in the nav,
  // so this runs on every page).
  useEffect(() => {
    let live = true;
    const poll = async () => {
      if (!getToken()) return; // signed out — the AuthGate is up anyway
      try {
        const { events, now } = await api.alertEvents(lastNotified.current);
        if (!live) return;
        if (events.length > 0) {
          lastNotified.current = now;
          setUnread(events.some((e) => e.ts > seenTs()));
          // Per-alert channel choice: browser === false means stay quiet here.
          const loud = events.filter((e) => e.browser !== false);
          setToasts((t) => [...t, ...loud].slice(-3));
          if (
            typeof Notification !== "undefined" &&
            Notification.permission === "granted"
          ) {
            for (const e of loud.slice(-3))
              new Notification(`${e.symbol} alert`, { body: e.message });
          }
          setTimeout(
            () => live && setToasts((t) => t.filter((x) => !loud.includes(x))),
            8000,
          );
        }
      } catch {
        /* backend unreachable or signed out — try again next tick */
      }
    };
    poll();
    const id = setInterval(poll, 30_000);
    return () => {
      live = false;
      clearInterval(id);
    };
  }, []);

  // Load full state when the panel opens; mark events seen.
  useEffect(() => {
    if (!open) return;
    setErr(null);
    setView("main");
    api
      .alerts()
      .then((s) => {
        setState(s);
        markSeen();
      })
      .catch(() => setErr("Couldn't load alerts."));
  }, [open]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  // Debounced symbol search for the add form.
  useEffect(() => {
    const query = q.trim();
    if (picked || query.length < 1) {
      setResults([]);
      return;
    }
    const id = setTimeout(async () => {
      try {
        setResults((await api.search(query)).results.slice(0, 5));
      } catch {
        setResults([]);
      }
    }, 200);
    return () => clearTimeout(id);
  }, [q, picked]);

  const addRule = async () => {
    if (!picked || !threshold) return;
    const [kind, direction] = cond.split(":");
    const t = parseFloat(threshold);
    if (!(t > 0)) return;
    try {
      setState(
        await api.alertCreate({
          symbol: picked.symbol,
          name: picked.name,
          kind,
          threshold: t,
          direction,
        }),
      );
      setPicked(null);
      setQ("");
      setThreshold("");
    } catch {
      setErr("Couldn't add that alert.");
    }
  };

  const patchRule = async (
    id: string,
    patch: Parameters<typeof api.alertUpdate>[1],
  ) => {
    try {
      setState(await api.alertUpdate(id, patch));
    } catch {
      setErr("Couldn't save that change.");
    }
  };

  const unit = CONDITIONS.find((c) => c.value === cond)?.unit ?? "%";
  const settings = state?.settings;
  const rules = state?.rules ?? [];
  const detail: AlertRule | undefined =
    view !== "main" && view !== "rules" ? rules.find((r) => r.id === view) : undefined;

  const patchSettings = async (patch: Parameters<typeof api.alertSettings>[0]) => {
    try {
      setState(await api.alertSettings(patch));
    } catch {
      setErr("Couldn't save settings.");
    }
  };

  const runTest = async (channel: "email" | "sms") => {
    setTestMsg((m) => ({ ...m, [channel]: "Sending…" }));
    try {
      const r = await api.alertTest(channel);
      setTestMsg((m) => ({
        ...m,
        [channel]: r.ok ? "Sent ✓ — check your inbox" : r.error || "Failed",
      }));
    } catch {
      setTestMsg((m) => ({ ...m, [channel]: "Failed to reach the server" }));
    }
  };

  const sendDigestNow = async (kind: "morning" | "evening") => {
    setTestMsg((m) => ({ ...m, [kind]: "Building your brief…" }));
    try {
      const r = await api.digestSend(kind);
      setTestMsg((m) => ({
        ...m,
        [kind]: r.ok ? "Sent ✓ — check your inbox" : r.error || "Failed",
      }));
    } catch {
      setTestMsg((m) => ({ ...m, [kind]: "Failed to reach the server" }));
    }
  };

  const notifPerm =
    typeof Notification !== "undefined" ? Notification.permission : "unsupported";
  const input =
    "rounded-lg border border-neutral-800 bg-neutral-950 text-sm placeholder:text-neutral-600 outline-none focus:border-neutral-600";

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label="Price alerts"
        className="relative flex h-9 w-9 items-center justify-center rounded-lg text-neutral-400 transition hover:bg-neutral-800/60 hover:text-neutral-100"
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
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
          <path d="M13.73 21a2 2 0 0 1-3.46 0" />
        </svg>
        {unread && (
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-amber-400" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 max-h-[82vh] w-[min(24rem,calc(100vw-1rem))] overflow-y-auto rounded-xl border border-neutral-800 bg-neutral-900 shadow-2xl">
          <header className="flex items-center justify-between gap-2 border-b border-neutral-800 px-4 py-3">
            <div>
              <h3 className="text-sm font-semibold">
                {view === "main"
                  ? "Price alerts"
                  : view === "rules"
                    ? "Your alerts"
                    : detail
                      ? `${detail.symbol} alert`
                      : "Alert"}
              </h3>
              <p className="mt-0.5 text-[11px] text-neutral-500">
                {view === "main"
                  ? "Checked every minute, 24/7 — even with this site closed."
                  : view === "rules"
                    ? "Tap an alert to choose where it goes."
                    : detail
                      ? condLabel(detail)
                      : ""}
              </p>
            </div>
            {view !== "main" && (
              <button
                onClick={() => setView(view === "rules" ? "main" : "rules")}
                className="shrink-0 text-xs text-neutral-400 transition hover:text-neutral-200"
              >
                ← Back
              </button>
            )}
          </header>

          {err && <p className="px-4 py-2 text-sm text-rose-400">{err}</p>}

          {/* ============== MAIN VIEW ============== */}
          {view === "main" && (
            <>
              {/* New alert */}
              <div className="border-b border-neutral-800 px-4 py-3">
                <div className="mb-1.5 text-xs font-semibold text-neutral-400">
                  New alert
                </div>
                <div className="relative">
                  <input
                    value={picked ? `${picked.name} (${picked.symbol})` : q}
                    onChange={(e) => {
                      setPicked(null);
                      setQ(e.target.value);
                    }}
                    placeholder="Search a ticker or company…"
                    className={`${input} w-full px-3 py-1.5`}
                  />
                  {results.length > 0 && !picked && (
                    <div className="absolute z-40 mt-1 w-full overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900 shadow-xl">
                      {results.map((r, i) => (
                        <button
                          key={`${r.symbol}-${i}`}
                          onClick={() => {
                            setPicked({ symbol: r.symbol, name: r.name });
                            setResults([]);
                          }}
                          className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left hover:bg-neutral-800"
                        >
                          <span className="min-w-0 truncate text-sm">{r.name}</span>
                          <span className="shrink-0 text-xs text-neutral-500">
                            {r.symbol}
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <select
                    value={cond}
                    onChange={(e) => setCond(e.target.value)}
                    className={`${input} flex-1 px-2 py-1.5`}
                  >
                    {CONDITIONS.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label} {c.unit === "%" ? "%" : "a price"}
                      </option>
                    ))}
                  </select>
                  <div className="relative w-24">
                    <input
                      value={threshold}
                      onChange={(e) => setThreshold(e.target.value)}
                      inputMode="decimal"
                      placeholder={unit === "%" ? "3" : "250"}
                      className={`${input} w-full py-1.5 pl-3 pr-7`}
                    />
                    <span className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-neutral-500">
                      {unit}
                    </span>
                  </div>
                  <button
                    onClick={addRule}
                    disabled={!picked || !(parseFloat(threshold) > 0)}
                    className="rounded-lg bg-neutral-100 px-3 py-1.5 text-sm font-medium text-neutral-900 transition hover:bg-white disabled:cursor-default disabled:opacity-40"
                  >
                    Add
                  </button>
                </div>
              </div>

              {/* Your alerts → its own view */}
              <div className="border-b border-neutral-800 px-4 py-3">
                <button
                  onClick={() => setView("rules")}
                  className="flex w-full items-center justify-between rounded-lg border border-neutral-800 bg-neutral-950/60 px-3 py-2.5 text-left transition hover:border-neutral-700 hover:bg-neutral-800/40"
                >
                  <span className="text-sm text-neutral-200">Your alerts</span>
                  <span className="flex items-center gap-2 text-xs text-neutral-500">
                    {rules.length || "none"}
                    <span aria-hidden>→</span>
                  </span>
                </button>
              </div>

              {/* Delivery destinations */}
              {settings && (
                <div className="px-4 py-3">
                  <div className="mb-1 text-xs font-semibold text-neutral-400">
                    Delivery
                  </div>
                  <p className="mb-2.5 text-[11px] leading-snug text-neutral-600">
                    Set your destinations here — then choose where each alert
                    goes inside Your alerts.
                  </p>

                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm text-neutral-300">
                      Browser notifications
                    </span>
                    {notifPerm === "granted" ? (
                      <span className="text-xs text-emerald-400">On</span>
                    ) : notifPerm === "denied" ? (
                      <span className="text-xs text-neutral-500">
                        Blocked in browser settings
                      </span>
                    ) : notifPerm === "unsupported" ? (
                      <span className="text-xs text-neutral-500">Unsupported</span>
                    ) : (
                      <button
                        onClick={() =>
                          Notification.requestPermission().then(() => setOpen(true))
                        }
                        className="rounded-md border border-neutral-700 px-2 py-1 text-xs text-neutral-300 hover:border-neutral-500"
                      >
                        Enable
                      </button>
                    )}
                  </div>

                  <div className="mt-2.5 flex items-center gap-2">
                    <input
                      defaultValue={settings.email_to}
                      onBlur={(e) => patchSettings({ email_to: e.target.value })}
                      placeholder="Email for alerts"
                      className={`${input} flex-1 px-3 py-1.5`}
                    />
                    <button
                      onClick={() => runTest("email")}
                      className="rounded-md border border-neutral-700 px-2 py-1.5 text-xs text-neutral-300 hover:border-neutral-500"
                    >
                      Test
                    </button>
                  </div>
                  {!state.email_configured && (
                    <p className="mt-1 text-[11px] leading-snug text-amber-400/90">
                      The server needs SMTP secrets first (ask Claude for the
                      one-time setup).
                    </p>
                  )}
                  {testMsg.email && (
                    <p className="mt-1 text-[11px] text-neutral-400">{testMsg.email}</p>
                  )}

                  <div className="mt-2 flex items-center gap-2">
                    <input
                      defaultValue={settings.sms_number}
                      onBlur={(e) => patchSettings({ sms_number: e.target.value })}
                      placeholder="Phone for texts"
                      inputMode="tel"
                      className={`${input} flex-1 px-3 py-1.5`}
                    />
                    <select
                      value={settings.sms_carrier}
                      onChange={(e) => patchSettings({ sms_carrier: e.target.value })}
                      className={`${input} px-2 py-1.5`}
                    >
                      {state.sms_carriers.map((c) => (
                        <option key={c} value={c}>
                          {c === "tmobile"
                            ? "T-Mobile"
                            : c === "att"
                              ? "AT&T"
                              : c === "uscellular"
                                ? "US Cellular"
                                : c[0].toUpperCase() + c.slice(1)}
                        </option>
                      ))}
                    </select>
                    <button
                      onClick={() => runTest("sms")}
                      className="rounded-md border border-neutral-700 px-2 py-1.5 text-xs text-neutral-300 hover:border-neutral-500"
                    >
                      Test
                    </button>
                  </div>
                  {testMsg.sms && (
                    <p className="mt-1 text-[11px] text-neutral-400">{testMsg.sms}</p>
                  )}

                  {(
                    [
                      {
                        kind: "morning" as const,
                        label: "☀️ Morning brief",
                        enabled: settings.digest_enabled,
                        time: settings.digest_time,
                        enabledKey: "digest_enabled" as const,
                        timeKey: "digest_time" as const,
                        blurb:
                          "Weekday mornings, before the open: futures, your watchlist pre-market, today's calendar, and what to watch.",
                      },
                      {
                        kind: "evening" as const,
                        label: "🌙 Evening wrap",
                        enabled: settings.evening_enabled,
                        time: settings.evening_time,
                        enabledKey: "evening_enabled" as const,
                        timeKey: "evening_time" as const,
                        blurb:
                          "Weekdays after the close: how the indices and your watchlist finished, and the story of the day.",
                      },
                    ]
                  ).map((ed) => (
                    <div key={ed.kind}>
                      <div className="mt-3 flex items-center justify-between gap-2">
                        <span className="text-sm text-neutral-300">{ed.label}</span>
                        <Toggle
                          on={ed.enabled}
                          onChange={() =>
                            patchSettings({ [ed.enabledKey]: !ed.enabled })
                          }
                        />
                      </div>
                      {ed.enabled && (
                        <div className="mt-2 space-y-1.5">
                          <div className="flex items-center gap-2">
                            <input
                              type="time"
                              defaultValue={ed.time}
                              onBlur={(e) =>
                                e.target.value &&
                                patchSettings({ [ed.timeKey]: e.target.value })
                              }
                              className={`${input} px-3 py-1.5`}
                            />
                            <span className="text-xs text-neutral-500">ET</span>
                            <div className="flex-1" />
                            <button
                              onClick={() => sendDigestNow(ed.kind)}
                              className="rounded-md border border-neutral-700 px-2 py-1.5 text-xs text-neutral-300 hover:border-neutral-500"
                            >
                              Send now
                            </button>
                          </div>
                          <p className="text-[11px] leading-snug text-neutral-600">
                            {ed.blurb}
                          </p>
                          {testMsg[ed.kind] && (
                            <p className="text-[11px] text-neutral-400">
                              {testMsg[ed.kind]}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </>
          )}

          {/* ============== RULES VIEW ============== */}
          {view === "rules" && (
            <div className="px-4 py-3">
              {rules.length === 0 && (
                <p className="py-2 text-sm text-neutral-600">
                  No alerts yet — add one from the main panel.
                </p>
              )}
              <div className="space-y-1.5">
                {rules.map((r) => (
                  <div
                    key={r.id}
                    className="flex items-center justify-between gap-2 rounded-lg border border-neutral-800/70 bg-neutral-950/60 px-3 py-2"
                  >
                    <button
                      onClick={() => setView(r.id)}
                      className="min-w-0 flex-1 text-left"
                    >
                      <div className="truncate text-sm text-neutral-200">
                        {r.name}{" "}
                        <span className="text-xs text-neutral-500">{r.symbol}</span>
                      </div>
                      <div className="text-xs text-neutral-500">
                        {condLabel(r)}
                        <span className="ml-1.5 text-neutral-600">
                          ·{" "}
                          {[
                            r.channels?.browser && "browser",
                            r.channels?.email && "email",
                            r.channels?.sms && "text",
                          ]
                            .filter(Boolean)
                            .join(" + ") || "nowhere"}
                        </span>
                      </div>
                    </button>
                    <div className="flex shrink-0 items-center gap-2">
                      <Toggle
                        on={r.enabled}
                        onChange={() => patchRule(r.id, { enabled: !r.enabled })}
                      />
                      <button
                        onClick={async () => setState(await api.alertDelete(r.id))}
                        aria-label={`Delete ${r.symbol} alert`}
                        className="px-1 text-neutral-500 transition hover:text-rose-400"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ============== DETAIL VIEW ============== */}
          {detail && (
            <div className="px-4 py-3">
              <div className="mb-1 text-xs font-semibold text-neutral-400">
                Send this alert via
              </div>
              {(
                [
                  { key: "browser" as const, label: "Browser notification" },
                  { key: "email" as const, label: "Email" },
                  { key: "sms" as const, label: "Text message" },
                ]
              ).map((ch) => (
                <div
                  key={ch.key}
                  className="mt-2 flex items-center justify-between gap-2"
                >
                  <span className="text-sm text-neutral-300">{ch.label}</span>
                  <Toggle
                    on={!!detail.channels?.[ch.key]}
                    onChange={() =>
                      patchRule(detail.id, {
                        channels: {
                          browser: !!detail.channels?.browser,
                          email: !!detail.channels?.email,
                          sms: !!detail.channels?.sms,
                          [ch.key]: !detail.channels?.[ch.key],
                        } as AlertChannels,
                      })
                    }
                  />
                </div>
              ))}
              <p className="mt-1.5 text-[11px] leading-snug text-neutral-600">
                Email and text go to the destinations set on the main panel.
              </p>

              {reportable(detail.symbol) && (
                <>
                  <div className="mt-4 mb-1 text-xs font-semibold text-neutral-400">
                    Earnings
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm text-neutral-300">
                      Heads-up when {detail.symbol} reports
                    </span>
                    <Toggle
                      on={detail.earnings_alert}
                      onChange={() =>
                        patchRule(detail.id, {
                          earnings_alert: !detail.earnings_alert,
                        })
                      }
                    />
                  </div>
                  <p className="mt-1.5 text-[11px] leading-snug text-neutral-600">
                    A morning notice (via the channels above) when {detail.symbol}{" "}
                    reports earnings today or tomorrow.
                  </p>
                </>
              )}

              <button
                onClick={async () => {
                  setState(await api.alertDelete(detail.id));
                  setView("rules");
                }}
                className="mt-4 w-full rounded-lg border border-neutral-800 px-3 py-1.5 text-xs text-neutral-400 transition hover:border-rose-900/50 hover:text-rose-300"
              >
                Delete this alert
              </button>
            </div>
          )}
        </div>
      )}

      {/* Toasts for fresh triggers */}
      {toasts.length > 0 && (
        <div className="fixed bottom-4 left-4 z-50 flex w-80 flex-col gap-2">
          {toasts.map((e) => (
            <div
              key={e.id}
              className="rounded-lg border border-amber-500/30 bg-neutral-900 px-4 py-3 text-sm text-neutral-200 shadow-2xl"
            >
              <div className="mb-0.5 text-xs font-semibold text-amber-400">
                {e.kind === "earnings" ? "Earnings heads-up" : "Price alert"}
              </div>
              {e.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
