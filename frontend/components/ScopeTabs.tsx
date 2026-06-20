"use client";

export type Scope = "day" | "week" | "month";

const SCOPES: { key: Scope; label: string }[] = [
  { key: "day", label: "Day" },
  { key: "week", label: "Week" },
  { key: "month", label: "Month" },
];

export default function ScopeTabs({
  scope,
  onChange,
}: {
  scope: Scope;
  onChange: (s: Scope) => void;
}) {
  return (
    <div className="inline-flex rounded-lg border border-neutral-800 bg-neutral-900 p-0.5">
      {SCOPES.map((s) => (
        <button
          key={s.key}
          onClick={() => onChange(s.key)}
          className={`px-3 py-1.5 text-sm rounded-md transition ${
            scope === s.key
              ? "bg-neutral-700 text-white"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}
