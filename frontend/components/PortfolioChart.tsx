"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { PortfolioHistory } from "@/lib/api";

/** Portfolio vs S&P 500, both indexed to 100 at the window start. */
export default function PortfolioChart({
  series,
}: {
  series: PortfolioHistory["series"];
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || series.length < 2) return;

    const chart: IChartApi = createChart(el, {
      width: el.clientWidth || 800,
      height: 300,
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
      timeScale: { borderColor: "#262626" },
      crosshair: { mode: 0 },
    });

    const toPoint = (t: string, v: number) => ({
      time: Math.floor(new Date(t + "T00:00:00").getTime() / 1000) as UTCTimestamp,
      value: v,
    });

    const port = chart.addAreaSeries({
      lineColor: "#f59e0b",
      topColor: "rgba(245,158,11,0.22)",
      bottomColor: "rgba(0,0,0,0)",
      lineWidth: 2,
      priceLineVisible: false,
    });
    port.setData(series.map((r) => toPoint(r.t, r.portfolio)));

    const spx = chart.addLineSeries({
      color: "#737373",
      lineWidth: 2,
      priceLineVisible: false,
    });
    spx.setData(series.map((r) => toPoint(r.t, r.spx)));

    chart.timeScale().fitContent();
    const fitTimer = setTimeout(() => chart.timeScale().fitContent(), 150);
    return () => {
      clearTimeout(fitTimer);
      chart.remove();
    };
  }, [series]);

  if (series.length < 2) return null;
  return (
    <div>
      <div ref={containerRef} className="w-full" style={{ height: 300 }} />
      <div className="mt-2 flex items-center gap-4 text-xs text-neutral-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-sm bg-amber-500/80" /> Your portfolio
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2 w-4 rounded-sm bg-neutral-500" /> S&amp;P 500
        </span>
        <span className="ml-auto">both indexed to 100 at the window start</span>
      </div>
    </div>
  );
}
