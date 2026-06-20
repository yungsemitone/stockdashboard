"use client";

import { useState } from "react";
import Link from "next/link";
import { api, type Article } from "@/lib/api";
import { usePoll } from "@/lib/usePoll";
import { fmtAgo } from "@/lib/format";

export default function NewsList({
  symbol,
  title = "Market News",
  limit,
}: {
  symbol?: string;
  title?: string;
  limit?: number;
}) {
  const { data, error } = usePoll<{ articles: Article[] }>(
    () => (symbol ? api.symbolNews(symbol) : api.news()),
    5 * 60 * 1000,
    [symbol ?? ""],
  );

  const [showAll, setShowAll] = useState(false);
  const articles = data?.articles ?? [];
  const shown = showAll ? articles : articles.slice(0, limit ?? 6);

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <header className="px-5 py-3 border-b border-neutral-800">
        <h3 className="font-semibold">{title}</h3>
      </header>
      {error && (
        <p className="px-5 py-4 text-sm text-rose-400">Couldn&apos;t load news.</p>
      )}
      {!error && articles.length === 0 && (
        <p className="px-5 py-4 text-sm text-neutral-500">No recent headlines.</p>
      )}
      <ul className="divide-y divide-neutral-800/70">
        {shown.map((a, i) => (
          <li key={`${a.id}-${i}`}>
            <Link
              href={`/article/${encodeURIComponent(a.id)}`}
              className="block px-5 py-3 hover:bg-neutral-800/40 transition"
            >
              <div className="text-sm text-neutral-100 leading-snug">{a.title}</div>
              <div className="mt-1 flex items-center gap-2 text-xs text-neutral-500">
                {a.publisher && <span>{a.publisher}</span>}
                {a.published && <span>· {fmtAgo(a.published)}</span>}
              </div>
            </Link>
          </li>
        ))}
      </ul>
      {articles.length > (limit ?? 6) && (
        <button
          onClick={() => setShowAll((s) => !s)}
          className="w-full px-5 py-2 text-xs text-neutral-400 hover:text-neutral-200 border-t border-neutral-800"
        >
          {showAll ? "Show less" : `Show all ${articles.length}`}
        </button>
      )}
    </section>
  );
}
