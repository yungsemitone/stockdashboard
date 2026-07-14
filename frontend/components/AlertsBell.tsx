"use client";

import { useEffect, useRef, useState } from "react";
import {
  api,
  getToken,
  type AlertEvent,
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

function ago(ts: number): string {
  const s = Math.max(0, Date.now() / 1000 - ts);
  if (s < 90) return "just now";
  if (s < 3600) return `${Math.round(s / 60)}m ago`;
  if (s < 86400) return `${Math.round(s / 3600)}h ago`;
  return new Date(ts * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
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

export default function AlertsBell() {
  const [open, setOpen] = useState(false);
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
          setToasts((t) => [...t, ...events].slice(-3));
          if (
            typeof Notification !== "undefined" &&
            Notification.permission === "granted"
          ) {
            for (const e of events.slice(-3))
              new Notification(`${e.symbol} price alert`, { body: e.message });
          }
          setTimeout(
            () => live && setToasts((t) => t.filter((x) => !events.includes(x))),
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
    api
      .alerts()
      .then((s) => {
        setState(s);
        if (s.events[0] && s.events[0].ts > seenTs()) setUnread(true);
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
        const r = await api.search(query);
        setResults(r.results.slice(0, 5));
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

  const unit = CONDITIONS.find((c) => c.value === cond)?.unit ?? "%";
  const settings = state?.settings;

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

  const sendDigestNow = async () => {
    setTestMsg((m) => ({ ...m, digest: "Building your brief…" }));
    try {
      const r = await api.digestSend();
      setTestMsg((m) => ({
        ...m,
        digest: r.ok ? "Sent ✓ — check your inbox" : r.error || "Failed",
      }));
    } catch {
      setTestMsg((m) => ({ ...m, digest: "Failed to reach the server" }));
    }
  };

  const notifPerm =
    typeof Notification !== "undefined" ? Notification.permission : "unsupported";

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
          <header className="border-b border-neutral-800 px-4 py-3">
            <h3 className="text-sm font-semibold">Price alerts</h3>
            <p className="mt-0.5 text-[11px] text-neutral-500">
              Checked every minute, 24/7 — even with this site closed.
            </p>
          </header>

          {err && <p className="px-4 py-2 text-sm text-rose-400">{err}</p>}

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
                className="w-full rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-sm placeholder:text-neutral-600 outline-none focus:border-neutral-600"
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
                className="flex-1 rounded-lg border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-sm outline-none focus:border-neutral-600"
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
                  className="w-full rounded-lg border border-neutral-800 bg-neutral-950 py-1.5 pl-3 pr-7 text-sm outline-none focus:border-neutral-600"
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

          {/* Rules */}
          <div className="border-b border-neutral-800 px-4 py-3">
            <div className="mb-1.5 text-xs font-semibold text-neutral-400">
              Your alerts
            </div>
            {!state && !err && (
              <p className="py-1 text-sm text-neutral-500">Loading…</p>
            )}
            {state?.rules.length === 0 && (
              <p className="py-1 text-sm text-neutral-600">
                None yet — add one above.
              </p>
            )}
            <div className="space-y-1.5">
              {state?.rules.map((r) => (
                <div
                  key={r.id}
                  className="flex items-center justify-between gap-2 rounded-lg border border-neutral-800/70 bg-neutral-950/60 px-3 py-2"
                >
                  <div className="min-w-0">
                    <div className="truncate text-sm text-neutral-200">
                      {r.name}{" "}
                      <span className="text-xs text-neutral-500">{r.symbol}</span>
                    </div>
                    <div className="text-xs text-neutral-500">{condLabel(r)}</div>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <Toggle
                      on={r.enabled}
                      onChange={async () =>
                        setState(await api.alertUpdate(r.id, { enabled: !r.enabled }))
                      }
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

          {/* Recent triggers */}
          {state && state.events.length > 0 && (
            <div className="border-b border-neutral-800 px-4 py-3">
              <div className="mb-1.5 text-xs font-semibold text-neutral-400">
                Recent triggers
              </div>
              <div className="space-y-1.5">
                {state.events.slice(0, 6).map((e) => (
                  <div key={e.id} className="text-xs leading-relaxed">
                    <span className="text-neutral-300">{e.message}</span>{" "}
                    <span className="text-neutral-600">· {ago(e.ts)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Delivery */}
          {settings && (
            <div className="px-4 py-3">
              <div className="mb-2 text-xs font-semibold text-neutral-400">
                Delivery
              </div>

              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-neutral-300">Browser notifications</span>
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

              <div className="mt-3 flex items-center justify-between gap-2">
                <span className="text-sm text-neutral-300">Email</span>
                <Toggle
                  on={settings.email_enabled}
                  onChange={() => patchSettings({ email_enabled: !settings.email_enabled })}
                />
              </div>
              {settings.email_enabled && (
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <input
                      defaultValue={settings.email_to}
                      onBlur={(e) => patchSettings({ email_to: e.target.value })}
                      placeholder="you@email.com"
                      className="flex-1 rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-sm placeholder:text-neutral-600 outline-none focus:border-neutral-600"
                    />
                    <button
                      onClick={() => runTest("email")}
                      className="rounded-md border border-neutral-700 px-2 py-1.5 text-xs text-neutral-300 hover:border-neutral-500"
                    >
                      Test
                    </button>
                  </div>
                  {!state.email_configured && (
                    <p className="text-[11px] leading-snug text-amber-400/90">
                      The server needs SMTP secrets first (ask Claude for the
                      one-time setup).
                    </p>
                  )}
                  {testMsg.email && (
                    <p className="text-[11px] text-neutral-400">{testMsg.email}</p>
                  )}
                </div>
              )}

              <div className="mt-3 flex items-center justify-between gap-2">
                <span className="text-sm text-neutral-300">Text message</span>
                <Toggle
                  on={settings.sms_enabled}
                  onChange={() => patchSettings({ sms_enabled: !settings.sms_enabled })}
                />
              </div>
              {settings.sms_enabled && (
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <input
                      defaultValue={settings.sms_number}
                      onBlur={(e) => patchSettings({ sms_number: e.target.value })}
                      placeholder="555 123 4567"
                      inputMode="tel"
                      className="flex-1 rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-sm placeholder:text-neutral-600 outline-none focus:border-neutral-600"
                    />
                    <select
                      value={settings.sms_carrier}
                      onChange={(e) => patchSettings({ sms_carrier: e.target.value })}
                      className="rounded-lg border border-neutral-800 bg-neutral-950 px-2 py-1.5 text-sm outline-none focus:border-neutral-600"
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
                  <p className="text-[11px] leading-snug text-neutral-600">
                    Free carrier email→text gateway — delivery depends on your
                    carrier (AT&T shut theirs down).
                  </p>
                  {testMsg.sms && (
                    <p className="text-[11px] text-neutral-400">{testMsg.sms}</p>
                  )}
                </div>
              )}

              <div className="mt-3 flex items-center justify-between gap-2">
                <span className="text-sm text-neutral-300">Morning digest</span>
                <Toggle
                  on={settings.digest_enabled}
                  onChange={() =>
                    patchSettings({ digest_enabled: !settings.digest_enabled })
                  }
                />
              </div>
              {settings.digest_enabled && (
                <div className="mt-2 space-y-1.5">
                  <div className="flex items-center gap-2">
                    <input
                      type="time"
                      defaultValue={settings.digest_time}
                      onBlur={(e) =>
                        e.target.value && patchSettings({ digest_time: e.target.value })
                      }
                      className="rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-sm outline-none focus:border-neutral-600"
                    />
                    <span className="text-xs text-neutral-500">ET</span>
                    <div className="flex-1" />
                    <button
                      onClick={sendDigestNow}
                      className="rounded-md border border-neutral-700 px-2 py-1.5 text-xs text-neutral-300 hover:border-neutral-500"
                    >
                      Send now
                    </button>
                  </div>
                  <p className="text-[11px] leading-snug text-neutral-600">
                    Weekday mornings by email: index futures, your watchlist
                    movers, today&apos;s calendar, and a short AI take.
                  </p>
                  {testMsg.digest && (
                    <p className="text-[11px] text-neutral-400">{testMsg.digest}</p>
                  )}
                </div>
              )}
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
                Price alert
              </div>
              {e.message}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
