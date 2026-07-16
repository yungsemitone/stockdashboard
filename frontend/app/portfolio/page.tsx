"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  api,
  type Portfolio,
  type PortfolioHistory,
  type SearchResult,
} from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import PortfolioChart from "@/components/PortfolioChart";
import { fmtPct, changeColor } from "@/lib/format";

const COLORS = [
  "#f59e0b", "#34d399", "#60a5fa", "#f472b6", "#a78bfa",
  "#fb7185", "#4ade80", "#38bdf8", "#facc15", "#c084fc",
];

const money = (n: number | null | undefined, digits = 2) =>
  n == null || Number.isNaN(n)
    ? "—"
    : `$${n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;

const signedMoney = (n: number | null | undefined) =>
  n == null || Number.isNaN(n) ? "—" : `${n >= 0 ? "+" : "-"}${money(Math.abs(n))}`;

export default function PortfolioPage() {
  const [pf, setPf] = useState<Portfolio | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const { data: polled } = usePoll<Portfolio>(() => api.portfolio(), 15_000, []);
  useEffect(() => {
    if (polled) setPf(polled);
  }, [polled]);

  const [range, setRange] = useState("6mo");
  // A transient data hiccup can return an empty comparison — retry quickly
  // until it fills, then relax to the slow poll.
  const [histPollMs, setHistPollMs] = useState(5 * 60 * 1000);
  const { data: hist } = usePoll<PortfolioHistory>(
    () => api.portfolioHistory(range),
    histPollMs,
    [range, pf?.holdings.length ?? 0],
  );
  useEffect(() => {
    setHistPollMs(hist && hist.series.length < 2 ? 15_000 : 5 * 60 * 1000);
  }, [hist]);

  // --- add/update form
  const [q, setQ] = useState("");
  const [picked, setPicked] = useState<{ symbol: string; name: string } | null>(null);
  const [results, setResults] = useState<SearchResult[]>([]);
  const [shares, setShares] = useState("");
  const [cost, setCost] = useState("");
  const boxRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node))
        setResults([]);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const addHolding = async () => {
    const s = parseFloat(shares);
    const c = parseFloat(cost);
    if (!picked || !(s > 0) || !(c >= 0)) return;
    try {
      setPf(await api.portfolioUpsert({ symbol: picked.symbol, shares: s, cost: c }));
      setPicked(null);
      setQ("");
      setShares("");
      setCost("");
      setErr(null);
    } catch {
      setErr("Couldn't save that holding.");
    }
  };

  const removeHolding = async (symbol: string) => {
    try {
      setPf(await api.portfolioRemove(symbol));
    } catch {
      setErr("Couldn't remove that holding.");
    }
  };

  const t = pf?.totals;
  const holdings = pf?.holdings ?? [];
  const input =
    "rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-1.5 text-sm placeholder:text-neutral-600 outline-none focus:border-neutral-600";

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Portfolio</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Your actual holdings — live value, P/L, and how you stack up
            against the S&amp;P.
          </p>
        </div>
        {t && holdings.length > 0 && (
          <div className="text-right">
            <div className="text-3xl font-bold tabular-nums">{money(t.value)}</div>
            <div className="text-sm tabular-nums">
              <span className={changeColor(t.day_pl)}>
                {signedMoney(t.day_pl)} ({fmtPct(t.day_pl_pct)})
              </span>{" "}
              <span className="text-neutral-500">today</span>
            </div>
            <div className="text-sm tabular-nums">
              <span className={changeColor(t.total_pl)}>
                {signedMoney(t.total_pl)} ({fmtPct(t.total_pl_pct)})
              </span>{" "}
              <span className="text-neutral-500">all time</span>
            </div>
          </div>
        )}
      </div>

      {err && <p className="mb-4 text-sm text-rose-400">{err}</p>}

      {/* Add / update */}
      <section className="mb-5 rounded-xl border border-neutral-800 bg-neutral-900/60 px-5 py-4">
        <div className="mb-2 text-xs font-semibold text-neutral-400">
          Add a holding{" "}
          <span className="font-normal text-neutral-600">
            (re-adding a symbol updates it)
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div ref={boxRef} className="relative min-w-56 flex-1">
            <input
              value={picked ? `${picked.name} (${picked.symbol})` : q}
              onChange={(e) => {
                setPicked(null);
                setQ(e.target.value);
              }}
              placeholder="Search a ticker or company…"
              className={`${input} w-full`}
            />
            {results.length > 0 && !picked && (
              <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900 shadow-xl">
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
                    <span className="shrink-0 text-xs text-neutral-500">{r.symbol}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <input
            value={shares}
            onChange={(e) => setShares(e.target.value)}
            inputMode="decimal"
            placeholder="Shares"
            className={`${input} w-24`}
          />
          <input
            value={cost}
            onChange={(e) => setCost(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && addHolding()}
            inputMode="decimal"
            placeholder="Avg cost $"
            className={`${input} w-28`}
          />
          <button
            onClick={addHolding}
            disabled={!picked || !(parseFloat(shares) > 0) || !(parseFloat(cost) >= 0)}
            className="rounded-lg bg-neutral-100 px-4 py-1.5 text-sm font-medium text-neutral-900 transition hover:bg-white disabled:cursor-default disabled:opacity-40"
          >
            Save
          </button>
        </div>
      </section>

      {pf && holdings.length === 0 && (
        <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 px-5 py-10 text-center text-sm text-neutral-500">
          No holdings yet — add your first position above and the live value,
          P/L, and the vs-S&amp;P chart appear here.
        </section>
      )}

      {holdings.length > 0 && (
        <>
          {/* Allocation bar */}
          <section className="mb-5 rounded-xl border border-neutral-800 bg-neutral-900/60 px-5 py-4">
            <div className="mb-2 text-xs font-semibold text-neutral-400">Allocation</div>
            <div className="flex h-3 w-full overflow-hidden rounded-full">
              {holdings.map((h, i) => (
                <div
                  key={h.symbol}
                  title={`${h.symbol} ${h.alloc_pct?.toFixed(1)}%`}
                  style={{
                    width: `${h.alloc_pct ?? 0}%`,
                    background: COLORS[i % COLORS.length],
                  }}
                />
              ))}
            </div>
            <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-xs">
              {holdings.map((h, i) => (
                <span key={h.symbol} className="flex items-center gap-1.5 text-neutral-400">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: COLORS[i % COLORS.length] }}
                  />
                  {h.symbol}{" "}
                  <span className="text-neutral-600">{h.alloc_pct?.toFixed(0)}%</span>
                </span>
              ))}
            </div>
          </section>

          {/* Holdings table */}
          <section className="mb-5 overflow-x-auto rounded-xl border border-neutral-800 bg-neutral-900/60">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-neutral-800 text-left text-xs text-neutral-500">
                  <th className="px-5 py-2.5 font-medium">Holding</th>
                  <th className="px-2 py-2.5 text-right font-medium">Shares</th>
                  <th className="px-2 py-2.5 text-right font-medium">Avg cost</th>
                  <th className="px-2 py-2.5 text-right font-medium">Price</th>
                  <th className="px-2 py-2.5 text-right font-medium">Value</th>
                  <th className="px-2 py-2.5 text-right font-medium">Today</th>
                  <th className="px-2 py-2.5 text-right font-medium">Total P/L</th>
                  <th className="px-3 py-2.5" />
                </tr>
              </thead>
              <tbody className="divide-y divide-neutral-800/70">
                {holdings.map((h) => (
                  <tr key={h.symbol} className="hover:bg-neutral-800/30 transition">
                    <td className="px-5 py-3">
                      <Link
                        href={`/asset/${encodeURIComponent(h.symbol)}`}
                        className="font-medium hover:text-white"
                      >
                        {h.symbol}
                      </Link>
                      <div className="max-w-40 truncate text-xs text-neutral-500">
                        {h.name}
                      </div>
                    </td>
                    <td className="px-2 py-3 text-right tabular-nums">{h.shares}</td>
                    <td className="px-2 py-3 text-right tabular-nums">{money(h.cost)}</td>
                    <td className="px-2 py-3 text-right tabular-nums">{money(h.price)}</td>
                    <td className="px-2 py-3 text-right font-medium tabular-nums">
                      {money(h.value, 0)}
                    </td>
                    <td className={`px-2 py-3 text-right tabular-nums ${changeColor(h.day_pl)}`}>
                      {signedMoney(h.day_pl)}
                      <div className="text-xs opacity-80">{fmtPct(h.change_pct)}</div>
                    </td>
                    <td className={`px-2 py-3 text-right tabular-nums ${changeColor(h.total_pl)}`}>
                      {signedMoney(h.total_pl)}
                      <div className="text-xs opacity-80">{fmtPct(h.total_pl_pct)}</div>
                    </td>
                    <td className="px-3 py-3 text-right">
                      <button
                        onClick={() => removeHolding(h.symbol)}
                        className="rounded-md border border-neutral-800 px-2 py-1 text-xs text-neutral-400 hover:border-rose-900/50 hover:text-rose-300"
                        title="Remove holding"
                      >
                        ✕
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          {/* vs S&P chart */}
          <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 px-5 py-4">
            <div className="mb-3 flex items-center justify-between">
              <div className="text-xs font-semibold text-neutral-400">
                Performance vs the S&amp;P 500
              </div>
              <div className="flex gap-1">
                {["1mo", "6mo", "1y"].map((r) => (
                  <button
                    key={r}
                    onClick={() => setRange(r)}
                    className={`rounded-md px-2.5 py-1 text-xs transition ${
                      range === r
                        ? "bg-neutral-700 text-white"
                        : "text-neutral-400 hover:text-neutral-200"
                    }`}
                  >
                    {r.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>
            {hist?.series && hist.series.length >= 2 ? (
              <PortfolioChart series={hist.series} />
            ) : (
              <div className="flex h-[300px] items-center justify-center text-sm text-neutral-600">
                Loading comparison…
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
