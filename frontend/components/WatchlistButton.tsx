"use client";

import { useEffect, useRef, useState } from "react";
import { api, type WatchList } from "@/lib/api";

export default function WatchlistButton({ symbol }: { symbol: string }) {
  const [lists, setLists] = useState<WatchList[] | null>(null);
  const [open, setOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let active = true;
    api
      .watchlists()
      .then((p) => active && setLists(p.lists))
      .catch(() => active && setLists([]));
    return () => {
      active = false;
    };
  }, [symbol]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const inAny = lists?.some((l) => l.symbols.includes(symbol)) ?? false;

  const toggle = async (name: string, isIn: boolean) => {
    const p = isIn
      ? await api.watchlistRemoveItem(name, symbol)
      : await api.watchlistAddItem(name, symbol);
    setLists(p.lists);
  };

  const create = async () => {
    const name = newName.trim();
    if (!name) return;
    await api.watchlistCreate(name);
    const p = await api.watchlistAddItem(name, symbol);
    setLists(p.lists);
    setNewName("");
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        disabled={lists === null}
        className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition disabled:opacity-50 ${
          inAny
            ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
            : "border-neutral-800 bg-neutral-900 text-neutral-300 hover:text-white"
        }`}
      >
        <span>{inAny ? "★" : "☆"}</span>
        Watchlist
        <span className="text-neutral-500">▾</span>
      </button>

      {open && lists && (
        <div className="absolute right-0 z-30 mt-1 w-64 rounded-lg border border-neutral-800 bg-neutral-900 p-2 shadow-xl">
          <div className="px-2 py-1 text-xs text-neutral-500">Save to lists</div>
          {lists.map((l) => {
            const isIn = l.symbols.includes(symbol);
            return (
              <button
                key={l.name}
                onClick={() => toggle(l.name, isIn)}
                className="flex w-full items-center justify-between rounded px-2 py-1.5 text-sm hover:bg-neutral-800"
              >
                <span className="truncate">{l.name}</span>
                <span className={isIn ? "text-amber-300" : "text-neutral-600"}>
                  {isIn ? "★" : "+"}
                </span>
              </button>
            );
          })}
          <div className="mt-1 flex gap-1 border-t border-neutral-800 pt-2">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && create()}
              placeholder="New list…"
              className="min-w-0 flex-1 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-sm outline-none focus:border-neutral-600"
            />
            <button
              onClick={create}
              className="rounded-md border border-neutral-800 px-2 py-1 text-sm text-neutral-300 hover:text-white"
            >
              Add
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
