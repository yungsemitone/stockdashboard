"use client";

import Link from "next/link";
import type { Quote, ClassSummary } from "@/lib/api";
import { fmtPct, changeColor, liveQuote } from "@/lib/format";
import LivePrice from "./LivePrice";

const SCOPE_WORD: Record<string, string> = {
  day: "today",
  week: "this week",
  month: "this month",
};

export default function ClassSection({
  label,
  items,
  summary,
  live,
}: {
  label: string;
  items: Quote[];
  summary?: ClassSummary;
  live?: Record<string, number>;
}) {
  const avg = summary?.average_pct ?? null;
  const scopeWord = summary ? SCOPE_WORD[summary.scope] ?? summary.scope : "";

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <header className="flex items-center justify-between px-5 py-3 border-b border-neutral-800">
        <h3 className="font-semibold">{label}</h3>
        {avg != null && (
          <span className={`text-sm font-medium ${changeColor(avg)}`}>
            avg {fmtPct(avg)}{" "}
            <span className="text-neutral-500 font-normal">{scopeWord}</span>
          </span>
        )}
      </header>

      {items.length === 0 ? (
        <div className="px-5 py-6 text-sm text-neutral-600">Loading…</div>
      ) : (
        <div className="divide-y divide-neutral-800/70">
          {items.map((q) => {
            const { price, change_pct } = liveQuote(q, live?.[q.symbol]);
            return (
              <Link
                key={q.symbol}
                href={`/asset/${encodeURIComponent(q.symbol)}`}
                className="flex items-center justify-between px-5 py-3 hover:bg-neutral-800/40 transition"
              >
                <div className="min-w-0 pr-3">
                  <div className="font-medium truncate">{q.name}</div>
                  <div className="text-xs text-neutral-500">{q.symbol}</div>
                </div>
                <div className="text-right shrink-0">
                  <LivePrice
                    value={price}
                    level={q.is_level}
                    fx={q.is_fx}
                    className="tabular-nums"
                  />
                  <div className={`text-sm tabular-nums ${changeColor(change_pct)}`}>
                    {fmtPct(change_pct)}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </section>
  );
}
