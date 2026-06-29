"use client";

import { useEffect, useRef, useState } from "react";
import { chatStream } from "@/lib/api";

type ChatMsg = { role: "user" | "assistant"; content: string };
const STORAGE = "claude-chat-v1";

const CHIPS = [
  "Compare my watchlist",
  "What's moving today?",
  "What's on the economic calendar this week?",
  "How's the economy looking right now?",
];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    try {
      const s = localStorage.getItem(STORAGE);
      if (s) setMessages(JSON.parse(s));
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE, JSON.stringify(messages.slice(-50)));
    } catch {
      /* ignore */
    }
  }, [messages]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, loading, open]);

  const sendText = async (raw: string) => {
    const text = raw.trim();
    if (!text || loading) return;
    const next: ChatMsg[] = [...messages, { role: "user", content: text }];
    setMessages([...next, { role: "assistant", content: "" }]);
    setInput("");
    setLoading(true);
    setStatus(null);
    setError(null);
    let acc = "";
    try {
      await chatStream(next, (e) => {
        if (e.type === "delta" && e.text) {
          acc += e.text;
          setStatus(null);
          setMessages([...next, { role: "assistant", content: acc }]);
        } else if (e.type === "status") {
          setStatus(e.text ?? null);
        } else if (e.type === "error") {
          setError(e.text ?? "Something went wrong.");
        }
      });
      if (!acc) setMessages(next); // nothing came back; drop the empty bubble
    } catch {
      setMessages(next);
      setError("Couldn't reach Claude — try again in a moment.");
    } finally {
      setLoading(false);
      setStatus(null);
    }
  };

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendText(input);
    }
  };

  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        className="fixed bottom-5 right-5 z-40 inline-flex items-center gap-2 rounded-full border border-neutral-700 bg-neutral-900 px-4 py-2.5 text-sm font-medium text-neutral-100 shadow-xl hover:bg-neutral-800 transition"
        aria-label="Chat with Claude"
      >
        {open ? "Close" : "✦ Ask Claude"}
      </button>

      {open && (
        <div className="fixed bottom-20 right-5 z-40 flex h-[520px] max-h-[calc(100vh-7rem)] w-[370px] max-w-[calc(100vw-2.5rem)] flex-col overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-950 shadow-2xl">
          <header className="flex items-center justify-between border-b border-neutral-800 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-emerald-400">✦</span>
              <span className="font-semibold text-sm">Ask Claude</span>
            </div>
            <div className="flex items-center gap-3 text-xs">
              {messages.length > 0 && (
                <button
                  onClick={() => setMessages([])}
                  className="text-neutral-500 hover:text-neutral-300"
                >
                  Clear
                </button>
              )}
              <button
                onClick={() => setOpen(false)}
                className="text-neutral-500 hover:text-neutral-300"
              >
                ✕
              </button>
            </div>
          </header>

          <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3 space-y-3">
            {messages.length === 0 && (
              <div className="mt-1 space-y-3">
                <p className="text-sm text-neutral-500">
                  Ask me about the markets, a ticker, the economy — or anything
                  else. I can read your live dashboard and search the web.
                </p>
                <div className="flex flex-wrap gap-2">
                  {CHIPS.map((c) => (
                    <button
                      key={c}
                      onClick={() => sendText(c)}
                      className="rounded-full border border-neutral-800 bg-neutral-900 px-3 py-1.5 text-xs text-neutral-300 hover:border-neutral-600 hover:text-white transition"
                    >
                      {c}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) =>
              m.content.trim() || m.role === "user" ? (
                <div
                  key={i}
                  className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap ${
                      m.role === "user"
                        ? "bg-neutral-700 text-neutral-50"
                        : "bg-neutral-900 border border-neutral-800 text-neutral-200"
                    }`}
                  >
                    {m.content}
                  </div>
                </div>
              ) : null,
            )}
            {loading &&
              (status ||
                !messages[messages.length - 1]?.content?.trim()) && (
                <div className="flex justify-start">
                  <div className="inline-flex items-center gap-2 rounded-2xl border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-500">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                    {status || "Thinking…"}
                  </div>
                </div>
              )}
            {error && <p className="text-sm text-rose-400">{error}</p>}
          </div>

          <div className="border-t border-neutral-800 p-3">
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKey}
                rows={1}
                placeholder="Message Claude…"
                className="flex-1 resize-none rounded-lg border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm outline-none focus:border-neutral-600 max-h-28"
              />
              <button
                onClick={() => sendText(input)}
                disabled={loading || !input.trim()}
                className="rounded-lg bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 hover:bg-white disabled:opacity-40"
              >
                Send
              </button>
            </div>
            <p className="mt-1.5 text-[10px] text-neutral-600">
              Claude can make mistakes. Not financial advice.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
