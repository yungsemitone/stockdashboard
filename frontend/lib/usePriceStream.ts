"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import { useRefresh } from "./settings";

/**
 * Live prices for a set of symbols, by polling the backend's real-time quotes
 * every few seconds. (We poll instead of using a WebSocket because the Twelve
 * Data plan only allows 1 streaming symbol, whereas the REST API is unlimited —
 * so polling lets *every* symbol update.) Returns symbol -> latest price.
 */
export function usePriceStream(symbols: string[]): Record<string, number> {
  const [prices, setPrices] = useState<Record<string, number>>({});
  const { price: intervalMs } = useRefresh();
  const key = symbols.slice().sort().join(",");
  const symbolsRef = useRef(symbols);
  symbolsRef.current = symbols;

  useEffect(() => {
    if (symbols.length === 0) return;
    let active = true;

    const poll = async () => {
      try {
        const { quotes } = await api.quotes(symbolsRef.current);
        if (!active) return;
        setPrices((prev) => {
          const next = { ...prev };
          for (const [sym, q] of Object.entries(quotes)) {
            if (q && typeof q.price === "number") next[sym] = q.price;
          }
          return next;
        });
      } catch {
        /* keep last prices on a failed poll */
      }
    };

    poll();
    const id = setInterval(poll, intervalMs);
    return () => {
      active = false;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, intervalMs]);

  return prices;
}
