"use client";

import { useEffect, useState } from "react";
import { api, clearToken, setToken, setUser } from "@/lib/api";

/** Full-screen account gate: sign in or create an account (invite-code
 * protected). Shows whenever auth is required and this device has no session,
 * or any request 401s (expired/rotated). */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [locked, setLocked] = useState(false);
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [identifier, setIdentifier] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [pw, setPw] = useState("");
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // If the backend is unreachable, stay open — pages show their own errors.
    api
      .authStatus()
      .then((s) => {
        setLocked(s.required && !s.ok);
        if (s.required && !s.ok && !s.has_accounts) setMode("signup");
      })
      .catch(() => {});
    const onRequired = () => setLocked(true);
    window.addEventListener("auth:required", onRequired);
    return () => window.removeEventListener("auth:required", onRequired);
  }, []);

  const submit = async () => {
    if (busy) return;
    setBusy(true);
    setErr(null);
    try {
      const r =
        mode === "login"
          ? await api.authLogin(identifier, pw)
          : await api.authSignup({ email, username, password: pw, code });
      if (r.ok && r.token && r.user) {
        setToken(r.token);
        setUser(r.user);
        window.location.reload();
      } else {
        clearToken();
        setErr(r.error || "That didn't work — try again.");
      }
    } catch {
      setErr("Couldn't reach the server.");
    } finally {
      setBusy(false);
    }
  };

  const canSubmit =
    mode === "login"
      ? identifier.trim() && pw
      : email.trim() && username.trim() && pw.length >= 8;

  const input =
    "w-full rounded-lg border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm placeholder:text-neutral-600 outline-none focus:border-neutral-600";

  return (
    <>
      {children}
      {locked && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center overflow-y-auto bg-neutral-950/95 p-4 backdrop-blur-sm">
          <div className="w-full max-w-sm rounded-2xl border border-neutral-800 bg-neutral-900 p-6 shadow-2xl">
            <div className="text-2xl">📈</div>
            <h1 className="mt-2 text-lg font-semibold">Markets</h1>
            <p className="mt-1 text-sm text-neutral-500">
              {mode === "login"
                ? "Sign in to your dashboard."
                : "Create your account — you'll need the family code."}
            </p>

            <div className="mt-4 space-y-2.5">
              {mode === "login" ? (
                <input
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="Username or email"
                  autoFocus
                  className={input}
                />
              ) : (
                <>
                  <input
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="Email"
                    type="email"
                    autoFocus
                    className={input}
                  />
                  <input
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Username"
                    maxLength={24}
                    className={input}
                  />
                </>
              )}
              <input
                type="password"
                value={pw}
                onChange={(e) => setPw(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()}
                placeholder={mode === "signup" ? "Password (8+ characters)" : "Password"}
                className={input}
              />
              {mode === "signup" && (
                <input
                  type="password"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()}
                  placeholder="Family code"
                  className={input}
                />
              )}
            </div>

            {err && <p className="mt-2 text-sm text-rose-400">{err}</p>}

            <button
              onClick={submit}
              disabled={!canSubmit || busy}
              className="mt-4 w-full rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 transition hover:bg-white disabled:cursor-default disabled:opacity-40"
            >
              {busy ? "One sec…" : mode === "login" ? "Sign in" : "Create account"}
            </button>

            <button
              onClick={() => {
                setMode(mode === "login" ? "signup" : "login");
                setErr(null);
              }}
              className="mt-3 w-full text-center text-xs text-neutral-500 transition hover:text-neutral-300"
            >
              {mode === "login"
                ? "New here? Create an account"
                : "Already have an account? Sign in"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
