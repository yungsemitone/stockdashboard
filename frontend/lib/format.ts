// Display formatting helpers.

type PriceOpts = boolean | { level?: boolean; fx?: boolean };

export function fmtPrice(
  n: number | null | undefined,
  opts: PriceOpts = false,
): string {
  if (n == null || Number.isNaN(n)) return "—";
  const o = typeof opts === "boolean" ? { level: opts } : opts;
  if (o.fx) return n.toFixed(4);
  if (o.level) return n.toFixed(2);
  const abs = Math.abs(n);
  const maxFrac = abs >= 1 ? 2 : 4;
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: maxFrac,
  }).format(n);
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n >= 0 ? "+" : ""}${n.toFixed(2)}%`;
}

export function fmtCompact(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 2,
  }).format(n);
}

export function changeColor(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "text-neutral-400";
  if (n > 0) return "text-emerald-400";
  if (n < 0) return "text-rose-400";
  return "text-neutral-300";
}

export function fmtAgo(iso: string): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const mins = Math.round((Date.now() - then) / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  return `${days}d ago`;
}

export function fmtEventDate(iso: string): string {
  const d = new Date(iso + "T00:00:00");
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
  });
}

// Given a quote and a live streamed price, recompute the day's % change so the
// streamed price and its change stay consistent (derives prev close from the quote).
export function liveQuote(
  quote: { price: number | null; change: number | null; change_pct: number | null },
  live: number | undefined,
): { price: number | null; change_pct: number | null } {
  if (live == null) return { price: quote.price, change_pct: quote.change_pct };
  const prevClose =
    quote.price != null && quote.change != null ? quote.price - quote.change : null;
  if (prevClose && prevClose !== 0) {
    return { price: live, change_pct: ((live - prevClose) / prevClose) * 100 };
  }
  return { price: live, change_pct: quote.change_pct };
}

// Color an economic indicator's most recent change given which direction is "good".
export function indicatorColor(
  change: number | null,
  goodWhen: "low" | "high" | "neutral",
): string {
  if (change == null || change === 0 || goodWhen === "neutral")
    return "text-neutral-400";
  const good = goodWhen === "high" ? change > 0 : change < 0;
  return good ? "text-emerald-400" : "text-rose-400";
}
