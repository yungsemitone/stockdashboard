"use client";

import { useEffect, useRef, useState } from "react";
import { API_URL } from "./api";

/**
 * Subscribe to live price ticks for a set of Yahoo symbols via the backend's
 * WebSocket proxy. Returns a map of symbol -> latest streamed price. Symbols the
 * data feed doesn't cover simply never tick (callers keep their polled value).
 */
export function usePriceStream(symbols: string[]): Record<string, number> {
  const [prices, setPrices] = useState<Record<string, number>>({});
  const key = symbols.slice().sort().join(",");

  useEffect(() => {
    if (!symbols.length) return;
    const wsUrl = API_URL.replace(/^http/, "ws") + "/ws/prices";
    let closed = false;
    let ws: WebSocket | null = null;
    let reconnect: ReturnType<typeof setTimeout> | undefined;

    const connect = () => {
      if (closed) return;
      ws = new WebSocket(wsUrl);
      ws.onopen = () => ws?.send(JSON.stringify({ symbols }));
      ws.onmessage = (e) => {
        try {
          const d = JSON.parse(e.data);
          const price = typeof d.price === "string" ? parseFloat(d.price) : d.price;
          if (d.symbol && typeof price === "number" && !Number.isNaN(price)) {
            setPrices((p) => (p[d.symbol] === price ? p : { ...p, [d.symbol]: price }));
          }
        } catch {
          /* ignore */
        }
      };
      ws.onclose = () => {
        if (!closed) reconnect = setTimeout(connect, 3000);
      };
      ws.onerror = () => ws?.close();
    };

    connect();
    return () => {
      closed = true;
      if (reconnect) clearTimeout(reconnect);
      ws?.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  return prices;
}
