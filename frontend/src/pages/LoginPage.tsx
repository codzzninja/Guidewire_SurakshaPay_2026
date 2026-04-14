import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "../lib/api";
import { useAuth } from "../lib/AuthContext";

export default function LoginPage() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const t = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ phone, password }),
      });
      setToken(t.access_token);
      await refresh();
      nav("/", { replace: true });
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[100dvh] flex flex-col items-center justify-center p-5 pb-safe safe-pb relative overflow-hidden">
      {/* Dynamic background effects */}
      <div className="absolute top-[10%] left-[-10%] w-96 h-96 bg-brand/20 rounded-full blur-[100px] animate-pulse-glow" style={{ animationDuration: '4s' }} />
      <div className="absolute bottom-[10%] right-[-10%] w-96 h-96 bg-brand2/20 rounded-full blur-[100px] animate-pulse-glow" style={{ animationDuration: '5s', animationDelay: '1s' }} />

      <div className="glass-card w-full max-w-md p-8 sm:p-10 rounded-3xl relative z-10 animate-slide-up">
        <div className="mb-10 text-center">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-tr from-brand to-brand2 shadow-glow mb-5">
            <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <p className="font-display text-3xl font-bold text-ink tracking-tight">SurakshaPay</p>
          <p className="text-slate-400 mt-2 text-sm max-w-[250px] mx-auto leading-relaxed">
            Parametric income protection for delivery partners.
          </p>
        </div>
        
        <form onSubmit={submit} className="space-y-5" noValidate>
          <div>
            <label
              htmlFor="login-phone"
              className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 pl-1"
            >
              Mobile Number
            </label>
            <input
              id="login-phone"
              className="w-full rounded-2xl border border-glass-border bg-surface/50 text-ink px-4 py-3.5 text-lg outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/30 transition-all min-h-[50pxplaceholder-slate-500 font-medium"
              inputMode="numeric"
              autoComplete="tel"
              autoFocus
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="10-digit number"
              required
              aria-invalid={err ? "true" : undefined}
              aria-describedby={err ? "login-error" : undefined}
            />
          </div>
          <div>
            <label
              htmlFor="login-password"
              className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 pl-1"
            >
              Password
            </label>
            <input
              id="login-password"
              type="password"
              className="w-full rounded-2xl border border-glass-border bg-surface/50 text-ink px-4 py-3.5 outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/30 transition-all min-h-[50px] placeholder-slate-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
              aria-invalid={err ? "true" : undefined}
              aria-describedby={err ? "login-error" : undefined}
            />
          </div>
          
          {err ? (
            <div id="login-error" className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-xl flex items-center gap-2" role="alert">
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
              {err}
            </div>
          ) : null}
          
          <button
            type="submit"
            disabled={busy}
            className="w-full mt-2 rounded-2xl bg-gradient-to-r from-brand to-brand2 text-white font-bold text-base py-4 shadow-glow disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            {busy ? "Authenticating…" : "Sign in securely"}
          </button>
        </form>
        
        <p className="mt-8 text-center text-sm text-slate-400 font-medium">
          New here??{" "}
          <Link to="/register" className="text-brand hover:text-brand2 hover:underline transition-colors">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
