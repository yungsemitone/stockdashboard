"use client";

import { useEffect, useMemo, useState } from "react";
import { api, CLASS_ORDER, CLASS_LABELS, type Overview, type Summary } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { usePriceStream } from "@/lib/usePriceStream";
import ScopeTabs, { type Scope } from "@/components/ScopeTabs";
import MacroPanel from "@/components/MacroPanel";
import MoversNews from "@/components/MoversNews";
import ClassSection from "@/components/ClassSection";
import NewsList from "@/components/NewsList";
import EconCalendar from "@/components/EconCalendar";

export default function Home() {
  const [scope, setScope] = useState<Scope>("day");

  const { data: overview, error: ovErr, updatedAt } = usePoll<Overview>(
    () => api.overview(),
    30_000,
    [],
  );
  const { data: summary } = usePoll<Summary>(() => api.summary(scope), 60_000, [scope]);

  // Ticking clock so the "updated Xs ago" freshness indicator counts up live.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);
  const ageSec = updatedAt ? Math.round((now - updatedAt) / 1000) : null;
  const fresh = ageSec != null && ageSec < 90;

  const allSymbols = useMemo(
    () => (overview ? Object.values(overview).flat().map((q) => q.symbol) : []),
    [overview],
  );
  const live = usePriceStream(allSymbols);

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Market Dashboard</h1>
          <div className="flex items-center gap-2 text-sm mt-1">
            <span className="text-neutral-500">
              Live stocks, indices, commodities, bonds &amp; currencies
            </span>
            {ageSec != null && (
              <span
                className={`inline-flex items-center gap-1.5 ${
                  fresh ? "text-emerald-400" : "text-amber-400"
                }`}
                title={`Data last refreshed ${new Date(updatedAt!).toLocaleTimeString()}`}
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    fresh ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
                  }`}
                />
                {fresh ? "Live" : "Stale"} · updated{" "}
                {ageSec < 60 ? `${ageSec}s` : `${Math.round(ageSec / 60)}m`} ago
              </span>
            )}
          </div>
        </div>
        <ScopeTabs scope={scope} onChange={setScope} />
      </div>

      <div className="mb-6">
        <MacroPanel scope={scope} />
      </div>

      <div className="mb-6">
        <MoversNews scope={scope} />
      </div>

      {ovErr && (
        <div className="rounded-lg border border-rose-900/50 bg-rose-950/30 text-rose-300 text-sm px-4 py-3 mb-6">
          Couldn&apos;t reach the data API ({ovErr}). Make sure the backend is
          running on <code>http://localhost:8000</code>.
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2 grid gap-5 sm:grid-cols-2 self-start">
          {CLASS_ORDER.map((cls) => (
            <ClassSection
              key={cls}
              label={CLASS_LABELS[cls]}
              items={overview?.[cls] ?? []}
              summary={summary?.[cls]}
              live={live}
            />
          ))}
        </div>

        <div className="grid gap-5 self-start">
          <NewsList title="Market News" limit={6} />
          <EconCalendar limit={5} />
        </div>
      </div>
    </main>
  );
}
