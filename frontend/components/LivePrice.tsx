"use client";

import { useEffect, useRef, useState } from "react";
import { fmtPrice } from "@/lib/format";

/**
 * Renders a price that briefly flashes green/red when it ticks up/down. Used
 * for live-streamed values; falls back to a static render when nothing changes.
 */
export default function LivePrice({
  value,
  level,
  fx,
  className = "",
}: {
  value: number | null | undefined;
  level?: boolean;
  fx?: boolean;
  className?: string;
}) {
  const prev = useRef<number | null | undefined>(value);
  const [flash, setFlash] = useState<"" | "up" | "down">("");

  useEffect(() => {
    const p = prev.current;
    if (p != null && value != null && value !== p) {
      setFlash(value > p ? "up" : "down");
      const t = setTimeout(() => setFlash(""), 700);
      prev.current = value;
      return () => clearTimeout(t);
    }
    prev.current = value;
  }, [value]);

  const flashCls =
    flash === "up"
      ? "text-emerald-300"
      : flash === "down"
        ? "text-rose-300"
        : "";

  return (
    <span className={`transition-colors duration-200 ${flashCls} ${className}`}>
      {fmtPrice(value, { level, fx })}
    </span>
  );
}
