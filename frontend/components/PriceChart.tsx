"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { Candle } from "@/lib/api";

export default function PriceChart({
  candles,
  up,
}: {
  candles: Candle[];
  up: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart: IChartApi = createChart(el, {
      autoSize: true,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#a3a3a3",
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.06)" },
      },
      rightPriceScale: { borderColor: "#262626" },
      timeScale: {
        borderColor: "#262626",
        timeVisible: true,
        secondsVisible: false,
      },
      crosshair: { mode: 0 },
    });

    const lineColor = up ? "#34d399" : "#fb7185";
    const series = chart.addAreaSeries({
      lineColor,
      topColor: up ? "rgba(52,211,153,0.28)" : "rgba(251,113,133,0.28)",
      bottomColor: "rgba(0,0,0,0)",
      lineWidth: 2,
      priceLineVisible: false,
    });

    // De-dup + sort ascending; lightweight-charts requires strictly increasing time.
    const seen = new Set<number>();
    const data: { time: UTCTimestamp; value: number }[] = [];
    for (const c of candles) {
      if (c.close == null) continue;
      const t = Math.floor(new Date(c.time).getTime() / 1000);
      if (Number.isNaN(t) || seen.has(t)) continue;
      seen.add(t);
      data.push({ time: t as UTCTimestamp, value: c.close });
    }
    data.sort((a, b) => a.time - b.time);
    series.setData(data);
    chart.timeScale().fitContent();

    return () => chart.remove();
  }, [candles, up]);

  return <div ref={containerRef} className="w-full" style={{ height: 380 }} />;
}
