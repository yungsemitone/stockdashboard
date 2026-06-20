"use client";

import { useEffect, useRef, useState } from "react";

type PollResult<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  updatedAt: number | null;
};

/**
 * Fetch `fn()` immediately and then re-fetch every `intervalMs`, re-running
 * whenever `deps` change. Keeps the previous data visible while refreshing so
 * the UI doesn't flash.
 */
export function usePoll<T>(
  fn: () => Promise<T>,
  intervalMs: number,
  deps: unknown[] = [],
): PollResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [updatedAt, setUpdatedAt] = useState<number | null>(null);

  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let active = true;

    const run = async () => {
      try {
        const d = await fnRef.current();
        if (!active) return;
        setData(d);
        setError(null);
        setUpdatedAt(Date.now());
      } catch (e) {
        if (active) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (active) setLoading(false);
      }
    };

    setLoading(true);
    run();
    const id = setInterval(run, intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, updatedAt };
}
