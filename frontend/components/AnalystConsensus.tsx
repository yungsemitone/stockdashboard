"use client";

import { api, type Analysis } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";

export default function AnalystConsensus({ symbol }: { symbol: string }) {
  const { data } = usePoll<Analysis>(() => api.analysis(symbol), 60 * 60 * 1000, [
    symbol,
  ]);

  // Render nothing for assets with no analyst coverage (indices, FX, etc.).
  if (!data || !data.available || !data.distribution) return null;

  const d = data.distribution;
  const t = data.targets;
  const cases = [
    {
      label: "Why buy",
      text: data.bull,
      box: "border-emerald-900/40 bg-emerald-950/20",
      dot: "bg-emerald-400",
    },
    {
      label: "Why hold",
      text: data.hold,
      box: "border-amber-900/40 bg-amber-950/20",
      dot: "bg-amber-400",
    },
    {
      label: "Why sell",
      text: data.bear,
      box: "border-rose-900/40 bg-rose-950/20",
      dot: "bg-rose-400",
    },
  ];

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      <div className="flex items-center justify-between gap-3 mb-4">
        <div>
          <h3 className="font-semibold">Analyst Consensus</h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            {data.analysts} analysts
            {data.key ? ` · overall: ${data.key.replace(/_/g, " ")}` : ""}
          </p>
        </div>
        {data.ai && (
          <span className="shrink-0 text-xs rounded-full bg-emerald-500/15 text-emerald-300 px-2 py-0.5">
            AI summary
          </span>
        )}
      </div>

      <div className="flex h-3 w-full overflow-hidden rounded-full bg-neutral-800">
        <div className="bg-emerald-500" style={{ width: `${d.buy_pct}%` }} />
        <div className="bg-amber-500" style={{ width: `${d.hold_pct}%` }} />
        <div className="bg-rose-500" style={{ width: `${d.sell_pct}%` }} />
      </div>
      <div className="mt-2 flex justify-between text-xs font-medium">
        <span className="text-emerald-400">Buy {d.buy_pct.toFixed(0)}%</span>
        <span className="text-amber-400">Hold {d.hold_pct.toFixed(0)}%</span>
        <span className="text-rose-400">Sell {d.sell_pct.toFixed(0)}%</span>
      </div>

      {t?.mean != null && (
        <div className="mt-4 flex flex-wrap items-baseline gap-x-5 gap-y-1 text-sm">
          <div>
            <span className="text-neutral-500">Avg price target </span>
            <span className="tabular-nums font-medium">{t.mean.toFixed(2)}</span>
          </div>
          {data.upside_pct != null && (
            <div
              className={
                data.upside_pct >= 0 ? "text-emerald-400" : "text-rose-400"
              }
            >
              {data.upside_pct >= 0 ? "+" : ""}
              {data.upside_pct.toFixed(1)}% vs current
            </div>
          )}
          {t.low != null && t.high != null && (
            <div className="text-neutral-500 tabular-nums">
              Range {t.low.toFixed(0)}–{t.high.toFixed(0)}
            </div>
          )}
        </div>
      )}

      {data.summary && (
        <p className="mt-4 text-sm text-neutral-300 leading-relaxed">
          {data.summary}
        </p>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {cases.map((c) => (
          <div key={c.label} className={`rounded-lg border p-3 ${c.box}`}>
            <div className="flex items-center gap-2 mb-1.5">
              <span className={`h-2 w-2 rounded-full ${c.dot}`} />
              <span className="text-xs font-semibold text-neutral-200">
                {c.label}
              </span>
            </div>
            <p className="text-xs text-neutral-400 leading-relaxed">{c.text}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
