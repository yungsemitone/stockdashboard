import type { Metadata } from "next";
import { cookies } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import Nav from "@/components/Nav";
import AuthGate from "@/components/AuthGate";
import ChatWidget from "@/components/ChatWidget";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Market Dashboard",
  description:
    "Live stocks, indices, commodities & bonds with AI macro context.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Read the theme cookie at render time so the right theme is in the initial
  // HTML — no flash, and no client-side script.
  const theme = (await cookies()).get("theme")?.value;
  const themeClass = theme === "light" ? " theme-light" : "";

  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased${themeClass}`}
    >
      <body className="min-h-full flex flex-col">
        <AuthGate>
        <Nav />

        <div className="flex-1">{children}</div>

        <footer className="border-t border-neutral-800 py-4 text-center text-xs text-neutral-600">
          <span>
            Data via Yahoo Finance &amp; FRED · for personal research, not
            investment advice
          </span>
          <span className="mx-2 text-neutral-700">·</span>
          <a
            href="https://dad-dashboard.fly.dev"
            target="_blank"
            rel="noopener noreferrer"
            className="text-neutral-500 hover:text-neutral-300"
          >
            The Morning Desk ↗
          </a>
        </footer>

        <ChatWidget />
        </AuthGate>
      </body>
    </html>
  );
}
