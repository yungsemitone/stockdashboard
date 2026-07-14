"use client";

import { useEffect, useState } from "react";
import { api, clearToken, setToken, setUser } from "@/lib/api";

/** Full-screen account gate: sign in or create an account (invite-code
 * protected). Shows whenever auth is required and this device has no session,
 * or any request 401s (expired/rotated). */
export default function AuthGate({ children }: { children: React.ReactNode }) {
  const [locked, setLocked] = useState(false);
  const [mode, setMode] = useState<"login" | "signup" | "forgot" | "reset">("login");
  const [identifier, setIdentifier] = useState("");
  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [pw, setPw] = useState("");
  const [code, setCode] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [note, setNote] = useState<string | null>(null);
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
      if (mode === "forgot") {
        const r = await api.authForgot(identifier);
        if (r.ok) {
          setNote("If that account exists, a 6-digit code is on its way to its email.");
          setMode("reset");
        } else {
          setErr(r.error || "That didn't work — try again.");
        }
        return;
      }
      const r =
        mode === "login"
          ? await api.authLogin(identifier, pw)
          : mode === "signup"
            ? await api.authSignup({ email, username, password: pw, code })
            : await api.authReset(identifier, resetCode, pw);
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
      ? Boolean(identifier.trim() && pw)
      : mode === "signup"
        ? Boolean(email.trim() && username.trim() && pw.length >= 8)
        : mode === "forgot"
          ? Boolean(identifier.trim())
          : Boolean(identifier.trim() && resetCode.trim() && pw.length >= 8);

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
                : mode === "signup"
                  ? "Create your account — you'll need the family code."
                  : mode === "forgot"
                    ? "We'll email you a reset code."
                    : "Enter the code from your email and pick a new password."}
            </p>

            <div className="mt-4 space-y-2.5">
              {mode !== "signup" && (
                <input
                  value={identifier}
                  onChange={(e) => setIdentifier(e.target.value)}
                  placeholder="Username or email"
                  autoFocus={mode !== "reset"}
                  className={input}
                />
              )}
              {mode === "signup" && (
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
              {mode === "reset" && (
                <input
                  value={resetCode}
                  onChange={(e) => setResetCode(e.target.value)}
                  placeholder="6-digit code"
                  inputMode="numeric"
                  maxLength={6}
                  autoFocus
                  className={input}
                />
              )}
              {mode !== "forgot" && (
                <input
                  type="password"
                  value={pw}
                  onChange={(e) => setPw(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && canSubmit && submit()}
                  placeholder={
                    mode === "login" ? "Password" : "New password (8+ characters)"
                  }
                  className={input}
                />
              )}
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

            {note && !err && <p className="mt-2 text-sm text-emerald-400/90">{note}</p>}
            {err && <p className="mt-2 text-sm text-rose-400">{err}</p>}

            <button
              onClick={submit}
              disabled={!canSubmit || busy}
              className="mt-4 w-full rounded-lg bg-neutral-100 px-4 py-2 text-sm font-medium text-neutral-900 transition hover:bg-white disabled:cursor-default disabled:opacity-40"
            >
              {busy
                ? "One sec…"
                : mode === "login"
                  ? "Sign in"
                  : mode === "signup"
                    ? "Create account"
                    : mode === "forgot"
                      ? "Email me a code"
                      : "Set new password"}
            </button>

            {mode === "login" && (
              <button
                onClick={() => {
                  setMode("forgot");
                  setErr(null);
                  setNote(null);
                }}
                className="mt-3 w-full text-center text-xs text-neutral-500 transition hover:text-neutral-300"
              >
                Forgot password?
              </button>
            )}
            <button
              onClick={() => {
                setMode(mode === "login" ? "signup" : "login");
                setErr(null);
                setNote(null);
              }}
              className="mt-2 w-full text-center text-xs text-neutral-500 transition hover:text-neutral-300"
            >
              {mode === "login"
                ? "New here? Create an account"
                : "Back to sign in"}
            </button>
          </div>
        </div>
      )}
    </>
  );
}
