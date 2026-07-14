"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  ColorType,
  type IChartApi,
  type UTCTimestamp,
} from "lightweight-charts";
import type { Candle, SessionBounds } from "@/lib/api";

type Pt = { time: UTCTimestamp; value: number; session: string };

export default function PriceChart({
  candles,
  up,
  bounds,
}: {
  candles: Candle[];
  up: boolean;
  bounds?: SessionBounds | null;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const chart: IChartApi = createChart(el, {
      // Explicit initial size: autoSize alone measures asynchronously, so a
      // fitContent() on mount would run against a 0-width chart and be lost
      // (leaving the default right-anchored view).
      width: el.clientWidth || 800,
      height: 380,
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

    // lightweight-charts draws timestamps as UTC — shift intraday times so the
    // axis reads in the viewer's local timezone.
    const tzShift = -new Date().getTimezoneOffset() * 60;
    const toSec = (time: Candle["time"]): number | null => {
      if (typeof time === "number") return time + tzShift;
      const t = Math.floor(new Date(time).getTime() / 1000);
      return Number.isNaN(t) ? null : t;
    };

    // De-dup + sort ascending; lightweight-charts requires strictly increasing time.
    const seen = new Set<number>();
    const pts: Pt[] = [];
    for (const c of candles) {
      if (c.close == null) continue;
      const t = toSec(c.time);
      if (t == null || seen.has(t)) continue;
      seen.add(t);
      pts.push({ time: t as UTCTimestamp, value: c.close, session: c.session ?? "regular" });
    }
    pts.sort((a, b) => a.time - b.time);

    const lineColor = up ? "#34d399" : "#fb7185";
    const mkRegular = (last: boolean) =>
      chart.addAreaSeries({
        lineColor,
        topColor: up ? "rgba(52,211,153,0.28)" : "rgba(251,113,133,0.28)",
        bottomColor: "rgba(0,0,0,0)",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: last,
      });
    // Pre/after-hours: same line, dimmed — the Robinhood-style distinction.
    const mkExtended = (last: boolean) =>
      chart.addLineSeries({
        color: "#737373",
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: last,
      });

    // Whitespace points padding the day out to the session bounds, so the axis
    // always shows the full trading day (4:00–20:00 ET) proportionally — the
    // time scale spaces by bar, so the gaps must be filled with empty slots.
    // They're mixed into the real series (the supported whitespace pattern).
    type SeriesPoint = { time: UTCTimestamp; value?: number };
    const lastT = pts.length > 0 ? (pts[pts.length - 1].time as number) : 0;
    const firstT = pts.length > 0 ? (pts[0].time as number) : 0;
    const leading: SeriesPoint[] = [];
    const trailing: SeriesPoint[] = [];
    if (bounds && pts.length > 0) {
      for (let t = bounds.start + tzShift; t < firstT; t += 300)
        leading.push({ time: t as UTCTimestamp });
      for (let t = lastT + 300; t <= bounds.end + tzShift; t += 300)
        trailing.push({ time: t as UTCTimestamp });
    }

    const hasSessions = pts.some((p) => p.session !== "regular");
    if (!hasSessions) {
      const s = mkRegular(true);
      s.setData([
        ...leading,
        ...pts.map(({ time, value }) => ({ time, value })),
        ...trailing,
      ]);
    } else {
      // Split into consecutive same-session segments; each segment repeats the
      // previous point so the line stays visually connected across the joins.
      const segments: { session: string; data: SeriesPoint[] }[] = [];
      for (const p of pts) {
        const seg = segments[segments.length - 1];
        if (!seg || seg.session !== p.session) {
          const prev = seg?.data[seg.data.length - 1];
          segments.push({
            session: p.session,
            data: prev ? [prev, { time: p.time, value: p.value }] : [{ time: p.time, value: p.value }],
          });
        } else {
          seg.data.push({ time: p.time, value: p.value });
        }
      }
      if (segments.length > 0) {
        segments[0].data = [...leading, ...segments[0].data];
        const last = segments[segments.length - 1];
        last.data = [...last.data, ...trailing];
      }
      segments.forEach((seg, i) => {
        const isLast = i === segments.length - 1;
        const series = seg.session === "regular" ? mkRegular(isLast) : mkExtended(isLast);
        series.setData(seg.data);
      });
    }

    chart.timeScale().fitContent();
    // Re-fit once layout settles, in case the container resized after mount.
    const fitTimer = setTimeout(() => chart.timeScale().fitContent(), 150);

    return () => {
      clearTimeout(fitTimer);
      chart.remove();
    };
  }, [candles, up, bounds]);

  return <div ref={containerRef} className="w-full" style={{ height: 380 }} />;
}
