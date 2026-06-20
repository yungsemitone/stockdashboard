"use client";

import Link from "next/link";
import { api, type Overview } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import CurrencyConverter from "@/components/CurrencyConverter";
import { fmtPrice, fmtPct, changeColor } from "@/lib/format";

export default function CurrencyPage() {
  const { data: overview } = usePoll<Overview>(() => api.overview(), 30_000, []);
  const fx = overview?.currencies ?? [];

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Currencies & FX</h1>
        <p className="text-neutral-500 text-sm mt-1">
          Live exchange rates and a converter.
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        <CurrencyConverter />

        <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
          <header className="px-5 py-3 border-b border-neutral-800">
            <h3 className="font-semibold">Major Rates</h3>
          </header>
          <div className="divide-y divide-neutral-800/70">
            {fx.map((q) => (
              <Link
                key={q.symbol}
                href={`/asset/${encodeURIComponent(q.symbol)}`}
                className="flex items-center justify-between px-5 py-3 hover:bg-neutral-800/40 transition"
              >
                <span className="text-sm">{q.name}</span>
                <span className="text-right">
                  <span className="tabular-nums mr-3">
                    {fmtPrice(q.price, { level: q.is_level, fx: q.is_fx })}
                  </span>
                  <span className={`text-sm tabular-nums ${changeColor(q.change_pct)}`}>
                    {fmtPct(q.change_pct)}
                  </span>
                </span>
              </Link>
            ))}
            {fx.length === 0 && (
              <div className="px-5 py-6 text-sm text-neutral-600">Loading…</div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
