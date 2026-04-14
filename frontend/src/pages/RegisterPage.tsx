import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, setToken } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import { WORK_ZONES, zoneById } from "../data/zones";

export default function RegisterPage() {
  const nav = useNavigate();
  const { refresh } = useAuth();
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [platform, setPlatform] = useState<"swiggy" | "zomato">("swiggy");
  const [zoneId, setZoneId] = useState(WORK_ZONES[0].id);
  const [upiId, setUpiId] = useState("");
  const [hours, setHours] = useState(8);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const selectedZone = zoneById(zoneId) ?? WORK_ZONES[0];

  async function submit(e: FormEvent) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      const t = await api<{ access_token: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          phone,
          password,
          full_name: fullName,
          platform,
          zone_id: selectedZone.id,
          upi_id: upiId,
          avg_hours_per_day: hours,
          lat: selectedZone.lat,
          lon: selectedZone.lon,
        }),
      });
      setToken(t.access_token);
      await refresh();
      nav("/", { replace: true });
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-[100dvh] flex flex-col items-center justify-center py-10 px-4 pb-safe safe-pb relative overflow-hidden">
      {/* Dynamic background effects */}
      <div className="fixed top-[5%] left-[-5%] w-96 h-96 bg-brand/10 rounded-full blur-[120px] animate-pulse-glow" style={{ animationDuration: '6s' }} />
      <div className="fixed bottom-[5%] right-[-5%] w-96 h-96 bg-brand2/10 rounded-full blur-[120px] animate-pulse-glow" style={{ animationDuration: '7s', animationDelay: '2s' }} />

      <div className="glass-card w-full max-w-md p-6 sm:p-8 rounded-3xl relative z-10 animate-slide-up">
        <div className="mb-8 border-b border-glass-border pb-6">
          <Link to="/login" className="inline-flex items-center gap-1 text-sm text-brand font-bold uppercase tracking-wider hover:text-brand2 transition-colors">
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
            Back to login
          </Link>
          <h1 className="font-display text-3xl font-bold text-ink mt-5 tracking-tight">Join SurakshaPay</h1>
          <p className="text-slate-400 text-sm mt-1.5 leading-relaxed">
            Quick 2-minute setup. No long forms. Connect your UPI for instant parametric payouts.
          </p>
        </div>
        
        <form onSubmit={submit} className="space-y-5" noValidate>
          <div>
            <label htmlFor="reg-name" className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 pl-1">
              Full Name
            </label>
            <input
              id="reg-name"
              className="w-full rounded-2xl border border-glass-border bg-surface/50 text-ink px-4 py-3 outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/30 transition-all placeholder-slate-500 font-medium"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
              placeholder="As on bank account / UPI"
              autoComplete="name"
            />
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="reg-phone" className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 pl-1">
                Mobile
              </label>
              <input
                id="reg-phone"
                className="w-full rounded-2xl border border-glass-border bg-surface/50 text-ink px-4 py-3 outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/30 transition-all placeholder-slate-500"
                inputMode="numeric"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                required
                minLength={10}
                autoComplete="tel"
                placeholder="10-digit"
              />
            </div>
            <div>
              <label htmlFor="reg-password" className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 pl-1">
                Password
              </label>
              <input
                id="reg-password"
                type="password"
                className="w-full rounded-2xl border border-glass-border bg-surface/50 text-ink px-4 py-3 outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/30 transition-all placeholder-slate-500"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                autoComplete="new-password"
                placeholder="••••••••"
              />
            </div>
          </div>
          
          <div>
            <p className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-2 pl-1">
              Delivery Platform
            </p>
            <div className="flex gap-3" role="group">
              {(["swiggy", "zomato"] as const).map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setPlatform(p)}
                  className={`flex-1 rounded-2xl py-3 font-semibold capitalize border transition-all ${
                    platform === p
                      ? "border-brand bg-brand/10 text-brand shadow-[0_0_15px_rgba(56,189,248,0.15)] ring-1 ring-brand/50"
                      : "border-glass-border bg-surface/30 text-slate-400 hover:bg-surface/60"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          
          <div className="p-4 rounded-2xl bg-surface/30 border border-glass-border/50">
            <label htmlFor="reg-zone" className="block text-[11px] font-bold text-brand uppercase tracking-widest mb-1.5 pl-1">
              Primary Drop Zone (Live Weather API)
            </label>
            <select
              id="reg-zone"
              className="w-full rounded-xl border border-glass-border bg-surface text-ink px-3 py-3 outline-none focus:ring-2 focus:ring-brand/50 mb-2 font-medium"
              value={zoneId}
              onChange={(e) => setZoneId(e.target.value)}
            >
              {WORK_ZONES.map((z) => (
                <option key={z.id} value={z.id}>{z.label}</option>
              ))}
            </select>
            <p className="text-[10px] text-slate-400 leading-relaxed font-mono">
              Coordinates bounded: {selectedZone.lat.toFixed(4)}°, {selectedZone.lon.toFixed(4)}°
            </p>
          </div>
          
          <div className="grid grid-cols-[2fr_1fr] gap-4">
            <div>
              <label htmlFor="reg-upi" className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 pl-1">
                UPI ID (For Payouts)
              </label>
              <input
                id="reg-upi"
                className="w-full rounded-2xl border border-glass-border bg-surface/50 text-ink px-4 py-3 outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/30 transition-all font-mono text-sm placeholder-slate-500/50"
                value={upiId}
                onChange={(e) => setUpiId(e.target.value)}
                required
                placeholder="name@ybl"
                autoComplete="off"
              />
            </div>
            <div>
              <label htmlFor="reg-hours" className="block text-[11px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 pl-1 text-center">
                Avg Hrs/Day
              </label>
              <input
                id="reg-hours"
                type="number"
                step="0.5"
                min={2}
                max={14}
                className="w-full rounded-2xl border border-glass-border bg-surface/50 text-ink px-4 py-3 outline-none focus:ring-2 focus:ring-brand/50 focus:border-brand/30 transition-all text-center font-bold"
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
              />
            </div>
          </div>
          
          {err ? (
            <div className="bg-red-500/10 border border-red-500/20 text-red-400 text-sm px-4 py-3 rounded-xl flex items-center gap-2">
              <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
              {err}
            </div>
          ) : null}
          
          <button
            type="submit"
            disabled={busy}
            className="w-full mt-6 rounded-2xl bg-gradient-to-r from-accent to-brand text-white font-bold text-base py-4 shadow-glow disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            {busy ? "Securing Profile…" : "Initialize Protection"}
          </button>
        </form>
      </div>
    </div>
  );
}
