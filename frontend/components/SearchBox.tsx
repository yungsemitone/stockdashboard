"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, type SearchResult } from "@/lib/api";

export default function SearchBox() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const [loading, setLoading] = useState(false);
  const boxRef = useRef<HTMLDivElement>(null);

  // Debounced search as the user types.
  useEffect(() => {
    const query = q.trim();
    if (query.length < 1) {
      setResults([]);
      setOpen(false);
      return;
    }
    setLoading(true);
    const id = setTimeout(async () => {
      try {
        const r = await api.search(query);
        setResults(r.results);
        setActive(0);
        setOpen(true);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 200);
    return () => clearTimeout(id);
  }, [q]);

  // Close when clicking outside.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  const go = (symbol: string) => {
    setOpen(false);
    setQ("");
    setResults([]);
    router.push(`/asset/${encodeURIComponent(symbol)}`);
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (!open || results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      go(results[active].symbol);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  };

  return (
    <div ref={boxRef} className="relative w-full sm:w-72">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => results.length > 0 && setOpen(true)}
        onKeyDown={onKey}
        placeholder="Search any ticker or company…"
        className="w-full rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm text-neutral-100 placeholder:text-neutral-500 outline-none focus:border-neutral-600"
      />
      {open && (
        <div className="absolute z-30 mt-1 w-full overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900 shadow-xl">
          {results.map((r, i) => (
            <button
              key={`${r.symbol}-${i}`}
              onMouseEnter={() => setActive(i)}
              onClick={() => go(r.symbol)}
              className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left ${
                active === i ? "bg-neutral-800" : ""
              }`}
            >
              <span className="min-w-0 truncate text-sm text-neutral-100">
                {r.name}
              </span>
              <span className="shrink-0 text-xs text-neutral-500">
                {r.symbol}
                {r.type ? ` · ${r.type}` : ""}
              </span>
            </button>
          ))}
          {!loading && results.length === 0 && (
            <div className="px-3 py-2 text-sm text-neutral-500">No matches</div>
          )}
          {loading && results.length === 0 && (
            <div className="px-3 py-2 text-sm text-neutral-500">Searching…</div>
          )}
        </div>
      )}
    </div>
  );
}
