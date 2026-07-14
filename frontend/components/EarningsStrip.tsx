"use client";

import Link from "next/link";
import { api, type EarningsItem } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { fmtEventDate } from "@/lib/format";

export default function EarningsStrip() {
  const { data } = usePoll<{ upcoming: EarningsItem[] }>(
    () => api.earningsUpcoming(),
    30 * 60 * 1000,
    [],
  );
  const items = data?.upcoming ?? [];

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <header className="px-5 py-3 border-b border-neutral-800">
        <h3 className="font-semibold">Earnings — next two weeks</h3>
        <p className="text-xs text-neutral-500 mt-0.5">
          Your watchlist names with a report coming up
        </p>
      </header>
      {!data && <p className="px-5 py-4 text-sm text-neutral-500">Loading…</p>}
      {data && items.length === 0 && (
        <p className="px-5 py-4 text-sm text-neutral-600">
          Nothing on your watchlist reports in the next two weeks.
        </p>
      )}
      <div className="divide-y divide-neutral-800/70">
        {items.map((e) => (
          <Link
            key={e.symbol}
            href={`/asset/${encodeURIComponent(e.symbol)}`}
            className="flex items-center justify-between gap-3 px-5 py-2.5 hover:bg-neutral-800/40 transition"
          >
            <div className="min-w-0">
              <span className="text-sm font-medium">{e.symbol}</span>{" "}
              <span className="text-xs text-neutral-500 truncate">{e.name}</span>
            </div>
            <div className="shrink-0 flex items-center gap-2">
              <span className="text-xs text-neutral-400">{fmtEventDate(e.date)}</span>
              <span
                className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  e.days_away <= 1
                    ? "bg-amber-500/15 text-amber-400"
                    : "bg-neutral-800 text-neutral-400"
                }`}
              >
                {e.days_away === 0 ? "today" : e.days_away === 1 ? "tomorrow" : `in ${e.days_away}d`}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
