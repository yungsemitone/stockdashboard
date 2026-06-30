"use client";

import EconIndicators from "@/components/EconIndicators";
import EconRecap from "@/components/EconRecap";
import EconCalendar from "@/components/EconCalendar";
import NewsList from "@/components/NewsList";

export default function EconomyPage() {
  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6">
        <h1 className="text-2xl font-bold tracking-tight">Economy & Macro</h1>
        <p className="text-neutral-500 text-sm mt-1">
          The economic backdrop driving markets — key indicators, the release
          calendar, and what each means.
        </p>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <div className="lg:col-span-2 self-start space-y-5">
          <EconIndicators />
          <EconRecap />
        </div>
        <div className="grid gap-5 self-start">
          <EconCalendar />
          <NewsList title="Macro Headlines" limit={6} />
        </div>
      </div>
    </main>
  );
}
