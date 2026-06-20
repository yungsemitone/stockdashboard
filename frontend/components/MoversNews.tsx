"use client";

import Link from "next/link";
import { api, type MoversPayload } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { fmtPct, changeColor } from "@/lib/format";
import type { Scope } from "./ScopeTabs";

export default function MoversNews({ scope }: { scope: Scope }) {
  const { data } = usePoll<MoversPayload>(() => api.movers(scope), 60_000, [scope]);
  const movers = data?.movers ?? [];

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <header className="px-5 py-3 border-b border-neutral-800">
        <h3 className="font-semibold">What moved &amp; why</h3>
        <p className="text-xs text-neutral-500 mt-0.5">
          Biggest movers paired with a relevant headline
        </p>
      </header>
      {movers.length === 0 && (
        <p className="px-5 py-4 text-sm text-neutral-500">Loading…</p>
      )}
      <div className="grid sm:grid-cols-2 divide-y sm:divide-y-0 divide-neutral-800/70">
        {movers.map((m, idx) => (
          <div
            key={m.symbol}
            className={`px-5 py-3 border-neutral-800/70 ${
              idx % 2 === 0 ? "sm:border-r" : ""
            } ${idx >= 2 ? "sm:border-t" : ""}`}
          >
            <div className="flex items-baseline justify-between gap-3">
              <Link
                href={`/asset/${encodeURIComponent(m.symbol)}`}
                className="font-medium hover:text-white truncate"
              >
                {m.name}
              </Link>
              <span
                className={`text-sm tabular-nums shrink-0 ${changeColor(m.change_pct)}`}
              >
                {fmtPct(m.change_pct)}
              </span>
            </div>
            {m.headline ? (
              <Link
                href={`/article/${encodeURIComponent(m.headline.id)}`}
                className="mt-1 block text-xs text-neutral-400 hover:text-neutral-200 leading-snug"
              >
                {m.headline.title}
              </Link>
            ) : (
              <span className="mt-1 block text-xs text-neutral-600">
                No recent headline
              </span>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
