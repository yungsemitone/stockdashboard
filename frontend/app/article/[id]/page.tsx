"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { api, type ArticleDetail } from "@/lib/api";
import { fmtAgo } from "@/lib/format";

export default function ArticlePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [article, setArticle] = useState<ArticleDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .article(decodeURIComponent(id))
      .then((a) => active && setArticle(a))
      .catch((e) => active && setError(e instanceof Error ? e.message : String(e)));
    return () => {
      active = false;
    };
  }, [id]);

  return (
    <main className="mx-auto max-w-3xl px-4 py-8">
      <Link
        href="/"
        className="text-sm text-neutral-400 hover:text-neutral-200"
      >
        ← Back to dashboard
      </Link>

      {error && (
        <div className="mt-6 rounded-lg border border-neutral-800 bg-neutral-900/60 p-6 text-sm text-neutral-400">
          This article is no longer available. It may have aged out of the cache —
          head back to the{" "}
          <Link href="/" className="text-neutral-200 underline">
            dashboard
          </Link>{" "}
          for the latest headlines.
        </div>
      )}

      {!article && !error && (
        <div className="mt-6 space-y-3">
          <div className="h-8 w-3/4 animate-pulse rounded bg-neutral-800" />
          <div className="h-4 w-1/3 animate-pulse rounded bg-neutral-800" />
          <div className="h-24 w-full animate-pulse rounded bg-neutral-800" />
        </div>
      )}

      {article && (
        <article className="mt-6">
          <h1 className="text-2xl font-bold leading-tight">{article.title}</h1>
          <div className="mt-2 flex items-center gap-2 text-sm text-neutral-500">
            {article.publisher && <span>{article.publisher}</span>}
            {article.published && <span>· {fmtAgo(article.published)}</span>}
          </div>

          <div className="mt-5 rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-neutral-300">Summary</h2>
              {article.ai_summary && (
                <span className="text-xs rounded-full bg-emerald-500/15 text-emerald-300 px-2 py-0.5">
                  AI summary
                </span>
              )}
            </div>
            <p className="text-neutral-200 leading-relaxed">
              {article.summary || "No summary is available for this article."}
            </p>
          </div>

          {article.assets.length > 0 && (
            <div className="mt-5">
              <h2 className="text-sm font-semibold text-neutral-400 mb-2">
                Mentioned in this story
              </h2>
              <div className="flex flex-wrap gap-2">
                {article.assets.map((a) => (
                  <Link
                    key={a.symbol}
                    href={`/asset/${encodeURIComponent(a.symbol)}`}
                    className="inline-flex items-center gap-2 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-sm hover:border-neutral-600 transition"
                  >
                    <span className="text-neutral-100">{a.name}</span>
                    <span className="text-xs text-neutral-500">{a.symbol}</span>
                  </Link>
                ))}
              </div>
            </div>
          )}

          {article.url && (
            <a
              href={article.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 hover:bg-white transition"
            >
              Read the full article ↗
            </a>
          )}

          <p className="mt-4 text-xs text-neutral-600">
            Summary generated from the headline and publisher blurb — read the full
            article for complete details.
          </p>
        </article>
      )}
    </main>
  );
}
