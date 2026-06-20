"use client";

import { use, useMemo, useState } from "react";
import Link from "next/link";
import { api, type QuoteDetail, type History } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { usePriceStream } from "@/lib/usePriceStream";
import PriceChart from "@/components/PriceChart";
import WatchlistButton from "@/components/WatchlistButton";
import NewsList from "@/components/NewsList";
import AnalystConsensus from "@/components/AnalystConsensus";
import LivePrice from "@/components/LivePrice";
import { fmtPrice, fmtPct, fmtCompact, changeColor } from "@/lib/format";

const RANGES = ["1d", "5d", "1mo", "6mo", "1y", "5y", "max"] as const;

const CLASS_LABELS: Record<string, string> = {
  stocks: "Stock",
  indices: "Index",
  commodities: "Commodity",
  bonds: "Bond / Rate",
  currencies: "Currency",
};

export default function AssetPage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol: rawSymbol } = use(params);
  // Next gives the route segment still URL-encoded (e.g. "%5EGSPC"); decode it
  // so tickers like ^GSPC / GC=F resolve correctly and never show as raw codes.
  const symbol = decodeURIComponent(rawSymbol);
  const [range, setRange] = useState<string>("6mo");

  const { data: quote, error: qErr } = usePoll<QuoteDetail>(
    () => api.quote(symbol),
    30_000,
    [symbol],
  );
  const { data: hist } = usePoll<History>(
    () => api.history(symbol, range),
    60_000,
    [symbol, range],
  );

  const live = usePriceStream(useMemo(() => [symbol], [symbol]));
  const livePrice = live[symbol];

  const candles = hist?.candles ?? [];
  const level = quote?.is_level ?? false;
  const fx = quote?.is_fx ?? false;
  const priceOpts = { level, fx };

  // Blend the live streamed price into the header (recompute the day's change).
  const prevClose =
    quote?.previous_close ??
    (quote?.price != null && quote?.change != null ? quote.price - quote.change : null);
  const dispPrice = livePrice ?? quote?.price;
  const dispChange =
    livePrice != null && prevClose != null ? livePrice - prevClose : quote?.change;
  const dispPct =
    livePrice != null && prevClose != null && prevClose !== 0
      ? ((livePrice - prevClose) / prevClose) * 100
      : quote?.change_pct;
  const up = (dispPct ?? 0) >= 0;

  const stats: [string, string][] = quote
    ? [
        ["Open", fmtPrice(quote.open, priceOpts)],
        ["Previous close", fmtPrice(quote.previous_close, priceOpts)],
        [
          "Day range",
          quote.day_low != null && quote.day_high != null
            ? `${fmtPrice(quote.day_low, priceOpts)} – ${fmtPrice(quote.day_high, priceOpts)}`
            : "—",
        ],
        [
          "52-week range",
          quote.year_low != null && quote.year_high != null
            ? `${fmtPrice(quote.year_low, priceOpts)} – ${fmtPrice(quote.year_high, priceOpts)}`
            : "—",
        ],
        ["Volume", fmtCompact(quote.volume)],
        ["Market cap", quote.market_cap != null ? fmtCompact(quote.market_cap) : "—"],
      ]
    : [];

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      <div className="flex items-center justify-between gap-3">
        <Link href="/" className="text-sm text-neutral-400 hover:text-neutral-200">
          ← Back to dashboard
        </Link>
        <WatchlistButton symbol={symbol} />
      </div>

      <div className="mt-4 flex flex-wrap items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            {quote ? (
              <h1 className="text-2xl font-bold">{quote.name}</h1>
            ) : (
              <span className="inline-block h-7 w-56 animate-pulse rounded bg-neutral-800" />
            )}
            {quote?.asset_class && (
              <span className="text-xs rounded-full bg-neutral-800 text-neutral-300 px-2 py-0.5">
                {CLASS_LABELS[quote.asset_class] ?? quote.asset_class}
              </span>
            )}
          </div>
          <div className="text-neutral-500 text-sm mt-1">
            {symbol}
            {quote?.currency ? ` · ${quote.currency}` : ""}
          </div>
        </div>
        <div className="text-right">
          <LivePrice
            value={dispPrice}
            level={level}
            fx={fx}
            className="text-3xl font-bold tabular-nums"
          />
          <div
            className={`text-lg font-medium tabular-nums ${changeColor(dispPct)}`}
          >
            {dispChange != null &&
              `${dispChange >= 0 ? "+" : "-"}${fmtPrice(Math.abs(dispChange), priceOpts)} `}
            {fmtPct(dispPct)}
          </div>
        </div>
      </div>

      {qErr && (
        <p className="mt-4 text-rose-400 text-sm">
          Couldn&apos;t load {symbol}: {qErr}
        </p>
      )}

      <div className="mt-6 rounded-xl border border-neutral-800 bg-neutral-900/60 p-4">
        <div className="flex flex-wrap gap-1 mb-3">
          {RANGES.map((r) => (
            <button
              key={r}
              onClick={() => setRange(r)}
              className={`px-3 py-1 text-sm rounded-md transition ${
                range === r
                  ? "bg-neutral-700 text-white"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
        {candles.length > 0 ? (
          <PriceChart candles={candles} up={up} />
        ) : (
          <div className="h-[380px] flex items-center justify-center text-neutral-600 text-sm">
            Loading chart…
          </div>
        )}
      </div>

      <div className="mt-6 grid grid-cols-2 sm:grid-cols-3 gap-3">
        {stats.map(([k, v]) => (
          <div
            key={k}
            className="rounded-lg border border-neutral-800 bg-neutral-900/40 px-4 py-3"
          >
            <div className="text-xs text-neutral-500">{k}</div>
            <div className="mt-0.5 font-medium tabular-nums">{v}</div>
          </div>
        ))}
      </div>

      <div className="mt-6">
        <AnalystConsensus symbol={symbol} />
      </div>

      <div className="mt-6">
        <NewsList
          symbol={symbol}
          title={quote ? `${quote.name} — News` : "Related News"}
          limit={6}
        />
      </div>
    </main>
  );
}
