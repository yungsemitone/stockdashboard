"use client";

import { useEffect, useState } from "react";
import { api, clearToken, setToken } from "@/lib/api";

/** Full-screen login over the app whenever the family password is required
 * and this device doesn't have it (or it was rotated). Renders nothing extra
 * when auth is disabled server-side. */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [locked, setLocked] = useState(false);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // If the backend is unreachable, stay open — pages show their own errors.
    api
      .authStatus()
      .then((s) => setLocked(s.required && !s.ok))
      .catch(() => {});
    const onRequired = () => setLocked(true);
    window.addEventListener("auth:required", onRequired);
    return () => window.removeEventListener("auth:required", onRequired);
  }, []);

  const submit = async () => {
    if (!pw || busy) return;
    setBusy(true);
    setErr(null);
    try {
      const r = await api.authLogin(pw);
      if (r.ok) {
        if (r.token) setToken(r.token);
        // Full reload so every poll restarts with the token attached.
        window.location.reload();
      } else {
        clearToken();
        setErr("Wrong password — try again.");
      }
    } catch {
      setErr("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      {children}
      {locked && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-neutral-950/95 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-neutral-800 bg-neutral-900 p-6 shadow-2xl">
            <div className="text-2xl">📈</div>
            <h1 className="mt-2 text-lg font-semibold">Markets</h1>
            <p className="mt-1 text-sm text-neutral-500">
              Enter the family password to open the dashboard.
            </p>
            <input
              type="password"
              value={pw}
              onChange={(e) => setPw(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
              placeholder="Password"
              autoFocus
              className="mt-4 w-full rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm placeholder:text-neutral-600 outline-none focus:border-neutral-600"
            />
            {err && <p className="mt-2 text-sm text-rose-400">{err}</p>}
            <button
              onClick={submit}
              disabled={!pw || busy}
              className="mt-4 w-full rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 transition hover:bg-white disabled:cursor-default disabled:opacity-40"
            >
              {busy ? "Checking…" : "Unlock"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
