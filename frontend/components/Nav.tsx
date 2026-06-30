"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import SearchBox from "./SearchBox";
import SettingsMenu from "./SettingsMenu";

const LINKS = [
  { href: "/", label: "Dashboard" },
  { href: "/economy", label: "Economy" },
  { href: "/currency", label: "Currency" },
  { href: "/watchlist", label: "Watchlist" },
];

export default function Nav() {
  const path = usePathname();
  const isActive = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  return (
    <header className="sticky top-0 z-20 border-b border-neutral-800 bg-neutral-950/80 backdrop-blur">
      <div className="mx-auto max-w-6xl px-4 h-14 flex items-center gap-3">
        <Link href="/" className="font-semibold tracking-tight whitespace-nowrap">
          📈 Markets
        </Link>
        <nav className="hidden md:flex items-center gap-1 text-sm">
          {LINKS.map((l) => (
            <Link
              key={l.href}
              href={l.href}
              className={`px-3 py-1.5 rounded-md transition ${
                isActive(l.href)
                  ? "bg-neutral-800 text-white"
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              {l.label}
            </Link>
          ))}
        </nav>
        <div className="flex-1" />
        <SearchBox />
        <SettingsMenu />
      </div>
      <nav className="md:hidden flex items-center gap-1 text-sm px-4 pb-2 overflow-x-auto">
        {LINKS.map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className={`px-3 py-1 rounded-md whitespace-nowrap ${
              isActive(l.href)
                ? "bg-neutral-800 text-white"
                : "text-neutral-400"
            }`}
          >
            {l.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}
