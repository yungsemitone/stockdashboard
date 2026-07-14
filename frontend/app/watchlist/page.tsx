"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WatchList } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { usePriceStream } from "@/lib/usePriceStream";
import LivePrice from "@/components/LivePrice";
import { fmtChange, fmtPct, changeColor, liveQuote } from "@/lib/format";

export default function WatchlistPage() {
  const { data } = usePoll(() => api.watchlists(), 30_000, []);
  const [lists, setLists] = useState<WatchList[] | null>(null);
  const [active, setActive] = useState<string>("");
  const [newName, setNewName] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [renameVal, setRenameVal] = useState("");

  useEffect(() => {
    if (!data) return;
    setLists(data.lists);
    setActive((a) =>
      a && data.lists.some((l) => l.name === a) ? a : data.lists[0]?.name ?? "",
    );
  }, [data]);

  const current = lists?.find((l) => l.name === active) ?? null;
  const live = usePriceStream(current?.symbols ?? []);

  const createList = async () => {
    const name = newName.trim();
    if (!name) return;
    const p = await api.watchlistCreate(name);
    setLists(p.lists);
    setActive(name);
    setNewName("");
  };

  const deleteList = async () => {
    if (!current) return;
    const p = await api.watchlistDelete(current.name);
    setLists(p.lists);
    setActive(p.lists[0]?.name ?? "");
  };

  const doRename = async () => {
    const name = renameVal.trim();
    if (!current || !name) return;
    const p = await api.watchlistRename(current.name, name);
    setLists(p.lists);
    setActive(name);
    setRenaming(false);
  };

  const removeSym = async (symbol: string) => {
    if (!current) return;
    setLists((await api.watchlistRemoveItem(current.name, symbol)).lists);
  };

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <div className="mb-5">
        <h1 className="text-2xl font-bold tracking-tight">Watchlists</h1>
        <p className="text-neutral-500 text-sm mt-1">
          Organize what you track into named lists. Add tickers from the search
          bar or any asset page&apos;s ★ button.
        </p>
      </div>

      {/* List tabs + create */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        {lists?.map((l) => (
          <button
            key={l.name}
            onClick={() => {
              setActive(l.name);
              setRenaming(false);
            }}
            className={`rounded-lg border px-3 py-1.5 text-sm transition ${
              active === l.name
                ? "border-neutral-600 bg-neutral-800 text-white"
                : "border-neutral-800 bg-neutral-900 text-neutral-400 hover:text-neutral-200"
            }`}
          >
            {l.name}
            <span className="ml-2 text-xs text-neutral-500">{l.symbols.length}</span>
          </button>
        ))}
        <div className="flex items-center gap-1">
          <input
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createList()}
            placeholder="New list…"
            className="w-28 rounded-lg border border-neutral-800 bg-neutral-900 px-2 py-1.5 text-sm outline-none focus:border-neutral-600"
          />
          <button
            onClick={createList}
            className="rounded-lg border border-neutral-800 px-2.5 py-1.5 text-sm text-neutral-300 hover:text-white"
          >
            ＋
          </button>
        </div>
      </div>

      {/* Active list */}
      {current && (
        <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
          <header className="flex items-center justify-between gap-3 px-5 py-3 border-b border-neutral-800">
            {renaming ? (
              <div className="flex items-center gap-2">
                <input
                  autoFocus
                  value={renameVal}
                  onChange={(e) => setRenameVal(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && doRename()}
                  className="rounded-md border border-neutral-700 bg-neutral-950 px-2 py-1 text-sm outline-none"
                />
                <button onClick={doRename} className="text-sm text-emerald-300">
                  Save
                </button>
                <button
                  onClick={() => setRenaming(false)}
                  className="text-sm text-neutral-500"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <h2 className="font-semibold">{current.name}</h2>
            )}
            <div className="flex items-center gap-3 text-xs">
              <button
                onClick={() => {
                  setRenaming(true);
                  setRenameVal(current.name);
                }}
                className="text-neutral-400 hover:text-neutral-200"
              >
                Rename
              </button>
              <button
                onClick={deleteList}
                className="text-neutral-400 hover:text-rose-300"
              >
                Delete list
              </button>
            </div>
          </header>

          {current.quotes.length === 0 ? (
            <div className="px-5 py-10 text-center text-sm text-neutral-500">
              This list is empty. Add tickers from the search bar or an asset
              page&apos;s ★ button.
            </div>
          ) : (
            <div className="divide-y divide-neutral-800/70">
              {current.quotes.map((q) => (
                <div
                  key={q.symbol}
                  className="flex items-center justify-between px-5 py-3 hover:bg-neutral-800/40 transition"
                >
                  <Link
                    href={`/asset/${encodeURIComponent(q.symbol)}`}
                    className="min-w-0 pr-3 flex-1"
                  >
                    <div className="font-medium truncate">{q.name}</div>
                    <div className="text-xs text-neutral-500">{q.symbol}</div>
                  </Link>
                  <div className="text-right shrink-0 mr-4">
                    {(() => {
                      const { price, change, change_pct } = liveQuote(q, live[q.symbol]);
                      return (
                        <>
                          <LivePrice
                            value={price}
                            level={q.is_level}
                            fx={q.is_fx}
                            className="tabular-nums"
                          />
                          <div className={`text-sm tabular-nums ${changeColor(change_pct)}`}>
                            {change != null && (
                              <span>
                                {fmtChange(change, { level: q.is_level, fx: q.is_fx })}{" "}
                              </span>
                            )}
                            {change != null
                              ? `(${fmtPct(change_pct)})`
                              : fmtPct(change_pct)}
                          </div>
                        </>
                      );
                    })()}
                  </div>
                  <button
                    onClick={() => removeSym(q.symbol)}
                    className="shrink-0 rounded-md border border-neutral-800 px-2 py-1 text-xs text-neutral-400 hover:text-rose-300 hover:border-rose-900/50"
                    title="Remove from this list"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
