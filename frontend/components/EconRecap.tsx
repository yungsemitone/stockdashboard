"use client";

import { api, type EconomyRecap } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";

export default function EconRecap() {
  // Polls periodically; the backend only regenerates the recap when a new
  // economic number is actually released, so this just picks up fresh text.
  const { data, error } = usePoll<EconomyRecap>(
    () => api.economyRecap(),
    30 * 60 * 1000,
    [],
  );
  const recap = data?.recap;

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <header className="px-5 py-3 border-b border-neutral-800 flex items-start justify-between gap-3">
        <div>
          <h3 className="font-semibold">Daily Recap</h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            What the latest economic data is saying
            {data?.as_of ? ` · latest reading ${data.as_of}` : ""}
          </p>
        </div>
        {data?.ai && (
          <span className="shrink-0 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-400">
            AI recap
          </span>
        )}
      </header>
      <div className="px-5 py-4">
        {error && (
          <p className="text-sm text-rose-400">Couldn&apos;t load the recap.</p>
        )}
        {!error && !recap && (
          <p className="text-sm text-neutral-500">Writing the recap…</p>
        )}
        {recap && (
          <p className="text-sm text-neutral-300 leading-relaxed whitespace-pre-line">
            {recap}
          </p>
        )}
      </div>
    </section>
  );
}
