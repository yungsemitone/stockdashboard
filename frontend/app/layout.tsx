import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Nav from "@/components/Nav";
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

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
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
      </body>
    </html>
  );
}
