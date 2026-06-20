"use client";

import { api, type Indicator } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { indicatorColor } from "@/lib/format";

function fmtValue(i: Indicator): string {
  if (i.unit === "%") return `${i.value.toFixed(2)}%`;
  if (i.unit === "K") return `${i.value >= 0 ? "+" : ""}${i.value.toFixed(0)}K`;
  return i.value.toFixed(1);
}

function fmtChange(i: Indicator): string | null {
  if (i.change == null) return null;
  const sign = i.change >= 0 ? "+" : "";
  if (i.unit === "K") return `${sign}${i.change.toFixed(0)}K vs prior`;
  if (i.unit === "%") return `${sign}${i.change.toFixed(2)} vs prior`;
  return `${sign}${i.change.toFixed(1)} vs prior`;
}

export default function EconIndicators() {
  const { data, error } = usePoll<{ indicators: Indicator[] }>(
    () => api.economy(),
    30 * 60 * 1000,
    [],
  );
  const indicators = data?.indicators ?? [];

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <header className="px-5 py-3 border-b border-neutral-800">
        <h3 className="font-semibold">Economic Indicators</h3>
        <p className="text-xs text-neutral-500 mt-0.5">
          Latest US macro data (via FRED) — and why each matters
        </p>
      </header>
      {error && (
        <p className="px-5 py-4 text-sm text-rose-400">
          Couldn&apos;t load economic data.
        </p>
      )}
      {!error && indicators.length === 0 && (
        <p className="px-5 py-4 text-sm text-neutral-500">Loading…</p>
      )}
      <div className="grid sm:grid-cols-2 divide-y sm:divide-y-0 divide-neutral-800/70">
        {indicators.map((i, idx) => (
          <div
            key={i.id}
            className={`px-5 py-4 ${idx % 2 === 0 ? "sm:border-r" : ""} border-neutral-800/70 ${
              idx >= 2 ? "sm:border-t" : ""
            }`}
          >
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-sm text-neutral-300">{i.label}</span>
              <span className="text-lg font-semibold tabular-nums">
                {fmtValue(i)}
              </span>
            </div>
            <div className="flex items-center justify-between gap-3 mt-0.5">
              <span className="text-xs text-neutral-600">as of {i.as_of}</span>
              {fmtChange(i) && (
                <span
                  className={`text-xs tabular-nums ${indicatorColor(
                    i.change,
                    i.good_when,
                  )}`}
                >
                  {fmtChange(i)}
                </span>
              )}
            </div>
            <p className="mt-2 text-xs text-neutral-500 leading-relaxed">
              {i.implication}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
