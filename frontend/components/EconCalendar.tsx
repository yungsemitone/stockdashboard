"use client";

import { api, type CalEvent } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { fmtEventDate, fmtEventTimeLocal } from "@/lib/format";

const DOT: Record<string, string> = {
  high: "bg-rose-400",
  medium: "bg-amber-400",
  low: "bg-neutral-500",
};

export default function EconCalendar({ limit }: { limit?: number }) {
  const { data, error } = usePoll<{ events: CalEvent[] }>(
    () => api.calendar(),
    30 * 60 * 1000,
    [],
  );
  const events = data?.events ?? [];
  const shown = limit ? events.slice(0, limit) : events;

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <header className="px-5 py-3 border-b border-neutral-800">
        <h3 className="font-semibold">Economic Calendar</h3>
        <p className="text-xs text-neutral-500 mt-0.5">
          Upcoming US releases &amp; events — and their market implications
        </p>
      </header>
      {error && (
        <p className="px-5 py-4 text-sm text-rose-400">Couldn&apos;t load calendar.</p>
      )}
      {!error && events.length === 0 && (
        <p className="px-5 py-4 text-sm text-neutral-500">Loading…</p>
      )}
      <ul className="divide-y divide-neutral-800/70">
        {shown.map((e, i) => (
          <li key={`${e.date}-${e.name}-${i}`} className="px-5 py-3">
            <div className="flex items-start gap-3">
              <span
                className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${DOT[e.importance]}`}
                title={`${e.importance} importance`}
              />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm font-medium text-neutral-100">
                    {e.name}
                  </span>
                  <span className="shrink-0 text-xs text-neutral-400">
                    {e.approximate && (
                      <span className="text-neutral-600">≈ </span>
                    )}
                    {fmtEventDate(e.date)}
                  </span>
                </div>
                {e.time_et && (
                  <div className="text-xs text-neutral-600">
                    {fmtEventTimeLocal(e.date, e.time_et)}
                  </div>
                )}
                <p className="mt-1 text-xs text-neutral-500 leading-relaxed">
                  {e.implication}
                </p>
              </div>
            </div>
          </li>
        ))}
      </ul>
      <p className="px-5 py-2 text-[11px] text-neutral-600 border-t border-neutral-800">
        ≈ = recurring release on its typical day; exact date may shift a few days.
      </p>
    </section>
  );
}
