"use client";

import { api, type Macro } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import type { Scope } from "./ScopeTabs";

export default function MacroPanel({ scope }: { scope: Scope }) {
  const { data, error } = usePoll<Macro>(() => api.macro(scope), 5 * 60 * 1000, [scope]);

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      <div className="flex items-center justify-between gap-3 mb-3">
        <h2 className="text-lg font-semibold">Market Pulse — why it moved</h2>
        {data &&
          (data.ai ? (
            <span className="shrink-0 text-xs rounded-full bg-emerald-500/15 text-emerald-300 px-2 py-0.5">
              AI narrative
            </span>
          ) : (
            <span className="shrink-0 text-xs rounded-full bg-neutral-700/50 text-neutral-300 px-2 py-0.5">
              Auto summary
            </span>
          ))}
      </div>

      {error && (
        <p className="text-rose-400 text-sm">Couldn&apos;t load narrative: {error}</p>
      )}
      {!data && !error && <p className="text-neutral-500 text-sm">Loading…</p>}
      {data && (
        <p className="text-neutral-300 leading-relaxed whitespace-pre-line">
          {data.narrative}
        </p>
      )}
      {data && !data.ai && (
        <p className="mt-3 text-xs text-neutral-500">
          Tip: add an <code className="text-neutral-400">ANTHROPIC_API_KEY</code> in{" "}
          <code className="text-neutral-400">backend/.env</code> to get full AI
          explanations that tie moves to real-world macro events.
        </p>
      )}
    </section>
  );
}
