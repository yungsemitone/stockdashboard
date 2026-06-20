"use client";

import { useEffect, useState } from "react";
import { api, type ConvertResult } from "@/lib/api";

export default function CurrencyConverter() {
  const [currencies, setCurrencies] = useState<string[]>([
    "USD", "EUR", "GBP", "JPY",
  ]);
  const [from, setFrom] = useState("USD");
  const [to, setTo] = useState("EUR");
  const [amount, setAmount] = useState("100");
  const [result, setResult] = useState<ConvertResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.currencies().then((r) => setCurrencies(r.currencies)).catch(() => {});
  }, []);

  useEffect(() => {
    const amt = parseFloat(amount);
    if (Number.isNaN(amt)) {
      setResult(null);
      return;
    }
    setLoading(true);
    const id = setTimeout(async () => {
      try {
        setResult(await api.convert(from, to, amt));
      } catch {
        setResult(null);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(id);
  }, [from, to, amount]);

  const swap = () => {
    setFrom(to);
    setTo(from);
  };

  const selectCls =
    "rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm outline-none focus:border-neutral-600";

  return (
    <section className="rounded-xl border border-neutral-800 bg-neutral-900/60 p-5">
      <h3 className="font-semibold mb-4">Currency Converter</h3>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-xs text-neutral-500">Amount</label>
          <input
            type="number"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            className="w-32 rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm tabular-nums outline-none focus:border-neutral-600"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-neutral-500">From</label>
          <select value={from} onChange={(e) => setFrom(e.target.value)} className={selectCls}>
            {currencies.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <button
          onClick={swap}
          className="rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-300 hover:text-white"
          title="Swap"
        >
          ⇄
        </button>
        <div className="flex flex-col gap-1">
          <label className="text-xs text-neutral-500">To</label>
          <select value={to} onChange={(e) => setTo(e.target.value)} className={selectCls}>
            {currencies.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="mt-5 border-t border-neutral-800 pt-4">
        {result && result.result != null ? (
          <div>
            <div className="text-2xl font-bold tabular-nums">
              {result.amount.toLocaleString()} {result.base} ={" "}
              {result.result.toLocaleString(undefined, {
                maximumFractionDigits: 2,
              })}{" "}
              {result.quote}
            </div>
            <div className="text-sm text-neutral-500 mt-1 tabular-nums">
              1 {result.base} = {result.rate?.toFixed(4)} {result.quote}
            </div>
          </div>
        ) : (
          <div className="text-sm text-neutral-500">
            {loading ? "Converting…" : "Enter an amount to convert."}
          </div>
        )}
      </div>
    </section>
  );
}
