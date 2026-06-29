// Typed client for the FastAPI backend.

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

export type Quote = {
  symbol: string;
  name: string;
  is_level: boolean;
  is_fx?: boolean;
  asset_class?: string | null;
  price: number | null;
  change: number | null;
  change_pct: number | null;
};

export type Overview = Record<string, Quote[]>;

export type Mover = {
  symbol: string;
  name: string;
  price: number;
  change_pct: number;
  is_level: boolean;
  is_fx?: boolean;
};

export type ClassSummary = {
  scope: string;
  label: string;
  average_pct: number | null;
  gainers: Mover[];
  losers: Mover[];
  all: Mover[];
};

export type Summary = Record<string, ClassSummary>;

export type Macro = {
  scope: string;
  narrative: string;
  ai: boolean;
  error?: string;
};

export type Candle = {
  time: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
};

export type History = { symbol: string; range: string; candles: Candle[] };

export type QuoteDetail = {
  symbol: string;
  name: string;
  asset_class: string | null;
  is_level: boolean;
  is_fx?: boolean;
  price: number | null;
  previous_close: number | null;
  change: number | null;
  change_pct: number | null;
  open: number | null;
  day_high: number | null;
  day_low: number | null;
  year_high: number | null;
  year_low: number | null;
  market_cap: number | null;
  volume: number | null;
  currency: string | null;
};

export type SearchResult = {
  symbol: string;
  name: string;
  type: string;
  exchange: string;
};

export type Article = {
  id: string;
  title: string;
  summary: string;
  url: string;
  publisher: string;
  published: string;
  tickers: string[];
};

export type ArticleDetail = {
  id: string;
  title: string;
  publisher: string;
  published: string;
  url: string;
  summary: string;
  ai_summary: boolean;
  assets: { symbol: string; name: string }[];
};

export type MoverItem = Mover & {
  asset_class: string;
  headline: Article | null;
};

export type MoversPayload = { scope: string; movers: MoverItem[] };

export type Analysis = {
  symbol: string;
  name?: string;
  available: boolean;
  key?: string | null;
  mean?: number | null;
  analysts?: number;
  distribution?: {
    total: number;
    counts: Record<string, number>;
    buy: number;
    hold: number;
    sell: number;
    buy_pct: number;
    hold_pct: number;
    sell_pct: number;
  };
  targets?: {
    mean: number | null;
    high: number | null;
    low: number | null;
    median: number | null;
  };
  current?: number | null;
  upside_pct?: number | null;
  summary?: string;
  bull?: string;
  hold?: string;
  bear?: string;
  ai?: boolean;
};

export type WatchList = { name: string; symbols: string[]; quotes: Quote[] };
export type WatchlistsPayload = { lists: WatchList[] };

export type Indicator = {
  id: string;
  label: string;
  unit: string;
  value: number;
  prev: number | null;
  change: number | null;
  as_of: string;
  good_when: "low" | "high" | "neutral";
  implication: string;
};

export type CalEvent = {
  date: string;
  name: string;
  importance: "high" | "medium" | "low";
  approximate: boolean;
  time_et: string | null;
  implication: string;
};

export type ConvertResult = {
  base: string;
  quote: string;
  amount: number;
  rate: number | null;
  result: number | null;
};

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

const sym = (s: string) => encodeURIComponent(s);

export const api = {
  overview: () => get<Overview>("/api/overview"),
  quotes: (symbols: string[]) =>
    get<{ quotes: Record<string, { price: number | null; change: number | null; change_pct: number | null }> }>(
      `/api/quotes?symbols=${symbols.map(encodeURIComponent).join(",")}`,
    ),
  summary: (scope: string) => get<Summary>(`/api/summary?scope=${scope}`),
  macro: (scope: string) => get<Macro>(`/api/macro?scope=${scope}`),
  quote: (symbol: string) => get<QuoteDetail>(`/api/quote/${sym(symbol)}`),
  history: (symbol: string, range: string) =>
    get<History>(`/api/history/${sym(symbol)}?range=${range}`),
  search: (q: string) =>
    get<{ results: SearchResult[] }>(`/api/search?q=${encodeURIComponent(q)}`),
  news: () => get<{ articles: Article[] }>("/api/news"),
  symbolNews: (symbol: string) =>
    get<{ articles: Article[] }>(`/api/news/${sym(symbol)}`),
  economy: () => get<{ indicators: Indicator[] }>("/api/economy"),
  calendar: () => get<{ events: CalEvent[] }>("/api/calendar"),
  currencies: () => get<{ currencies: string[] }>("/api/currencies"),
  convert: (base: string, quote: string, amount: number) =>
    get<ConvertResult>(`/api/convert?base=${base}&quote=${quote}&amount=${amount}`),
  article: (id: string) => get<ArticleDetail>(`/api/article/${sym(id)}`),
  movers: (scope: string) => get<MoversPayload>(`/api/movers?scope=${scope}`),
  analysis: (symbol: string) => get<Analysis>(`/api/analysis/${sym(symbol)}`),
  watchlists: () => get<WatchlistsPayload>("/api/watchlists"),
  watchlistCreate: (name: string) =>
    send<WatchlistsPayload>("POST", "/api/watchlists", { name }),
  watchlistDelete: (name: string) =>
    send<WatchlistsPayload>("DELETE", `/api/watchlists/${sym(name)}`),
  watchlistRename: (name: string, newName: string) =>
    send<WatchlistsPayload>("PUT", `/api/watchlists/${sym(name)}`, { name: newName }),
  watchlistAddItem: (name: string, symbol: string) =>
    send<WatchlistsPayload>("POST", `/api/watchlists/${sym(name)}/items`, { symbol }),
  watchlistRemoveItem: (name: string, symbol: string) =>
    send<WatchlistsPayload>(
      "DELETE",
      `/api/watchlists/${sym(name)}/items/${sym(symbol)}`,
    ),
};

export type ChatEvent = { type: "delta" | "status" | "error" | "done"; text?: string };

/** Streams the agentic chat reply: calls onEvent for each delta/status/error. */
export async function chatStream(
  messages: { role: string; content: string }[],
  onEvent: (e: ChatEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_URL}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });
  if (!res.ok || !res.body) throw new Error(`${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const parts = buf.split("\n\n");
    buf = parts.pop() ?? "";
    for (const part of parts) {
      const line = part.trim();
      if (line.startsWith("data:")) {
        try {
          onEvent(JSON.parse(line.slice(5).trim()));
        } catch {
          /* ignore malformed event */
        }
      }
    }
  }
}

export const CLASS_ORDER = [
  "stocks",
  "indices",
  "commodities",
  "bonds",
  "currencies",
] as const;

export const CLASS_LABELS: Record<string, string> = {
  stocks: "Stocks",
  indices: "Indices",
  commodities: "Commodities",
  bonds: "Bonds & Rates",
  currencies: "Currencies",
};
