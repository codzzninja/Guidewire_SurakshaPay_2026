import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { apiAdmin } from "../lib/api";

const LS_KEY = "sp_admin_token";

/** Shared premium glass shell */
const shell = "rounded-2xl border border-white/10 bg-slate-900/40 backdrop-blur-xl shadow-2xl overflow-hidden relative";
const innerGlow = "absolute inset-0 bg-gradient-to-br from-white/[0.08] to-transparent pointer-events-none rounded-2xl";
const titleSm = "text-[11px] font-semibold uppercase tracking-widest text-slate-400";

function DetailsBlock({ label, children, open = false }: { label: string; children: ReactNode; open?: boolean }) {
  return (
    <details className="group mt-4 pt-4 border-t border-white/[0.08]" open={open}>
      <summary className="cursor-pointer list-none text-[12px] font-medium text-slate-400 hover:text-white flex items-center justify-between transition-colors [&::-webkit-details-marker]:hidden">
        {label}
        <span className="inline-block w-4 h-4 rounded-full bg-white/5 flex items-center justify-center group-open:bg-white/10 transition-colors">
          <svg className="w-2 h-2 text-slate-400 group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M19 9l-7 7-7-7" />
          </svg>
        </span>
      </summary>
      <div className="mt-3 text-[12px] text-slate-300 leading-relaxed bg-slate-950/30 p-3 rounded-lg border border-white/5">{children}</div>
    </details>
  );
}

function MetricCard({ title, value, subtext, highlight = false, badge }: { title: string, value: string | ReactNode, subtext?: string, highlight?: boolean, badge?: ReactNode }) {
  return (
    <div className={`relative p-5 rounded-2xl border ${highlight ? 'border-brand/30 bg-brand/5' : 'border-white/[0.08] bg-slate-900/30'} flex flex-col justify-between overflow-hidden transition-colors hover:bg-slate-800/40`}>
      {highlight && <div className="absolute top-0 right-0 w-32 h-32 bg-brand/10 blur-3xl rounded-full -mr-10 -mt-10 pointer-events-none" />}
      <div className="flex justify-between items-start mb-2 relative z-10">
        <p className="text-[11px] font-medium uppercase tracking-wider text-slate-400">{title}</p>
        {badge}
      </div>
      <div className="relative z-10 mt-auto">
        <p className={`font-display font-bold tabular-nums tracking-tight ${highlight ? 'text-4xl text-brand' : 'text-3xl text-white'}`}>{value}</p>
        {subtext && <p className="text-xs text-slate-500 mt-1">{subtext}</p>}
      </div>
    </div>
  );
}

export default function InsurerDashboardPage() {
  const [token, setToken] = useState(() => localStorage.getItem(LS_KEY) ?? "");
  const [data, setData] = useState<Record<string, unknown> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    setData(null);
    try {
      const j = await apiAdmin<Record<string, unknown>>("/analytics/admin/summary", token.trim());
      setData(j);
      localStorage.setItem(LS_KEY, token.trim());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not load");
    } finally {
      setLoading(false);
    }
  }, [token]);
  
  useEffect(() => {
    // Auto-load on mount for testing convenience as requested
    void load();
  }, [load]);

  const portfolio = data?.portfolio as Record<string, unknown> | undefined;
  const lossRatio = portfolio?.loss_ratio as Record<string, unknown> | undefined;
  const lossRatioAllTime = portfolio?.loss_ratio_all_time as Record<string, unknown> | undefined;
  const nowcast = data?.environment_nowcast_24h as Record<string, unknown> | undefined;
  const weekAhead = data?.predictive_week_ahead_disruption as Record<string, unknown> | undefined;
  const socialFeed = weekAhead?.social_disruption_feed as Record<string, unknown> | undefined;
  const zonesTop = data?.zones_top as { zone_id: string; workers: number }[] | undefined;

  const nowcastRollup = nowcast?.rollup_24h as Record<string, unknown> | undefined;
  const nowcastMarkets = nowcast?.markets as Record<string, unknown>[] | undefined;
  const weekRollup = weekAhead?.rollup as Record<string, unknown> | undefined;
  const claimForecast = weekAhead?.predicted_claim_activity_next_7d as Record<string, unknown> | undefined;
  const claimByZone = (claimForecast?.by_zone as Record<string, unknown>[] | undefined) ?? [];
  const predictionCenter = data?.admin_prediction_center as Record<string, unknown> | undefined;
  const highRiskDays = (predictionCenter?.high_risk_forecast_days as Record<string, unknown>[] | undefined) ?? [];
  const zonesRanked = (predictionCenter?.zones_ranked_by_combined_risk as Record<string, unknown>[] | undefined) ?? [];
  const fraudSnap = predictionCenter?.fraud_portfolio_snapshot_30d as Record<string, unknown> | undefined;

  const zoneRows: Record<string, unknown>[] =
    zonesRanked.length > 0 ? zonesRanked : claimByZone.map((z, i) => ({ ...z, rank: i + 1 }));

  const tierBadgeClass = (tier: string) => {
    switch (tier) {
      case "critical":
        return "bg-rose-500/20 text-rose-300 ring-1 ring-rose-500/30 drop-shadow-[0_0_8px_rgba(244,63,94,0.3)]";
      case "high":
        return "bg-orange-500/20 text-orange-300 ring-1 ring-orange-500/30 drop-shadow-[0_0_8px_rgba(249,115,22,0.3)]";
      case "moderate":
        return "bg-amber-500/20 text-amber-300 ring-1 ring-amber-500/30 drop-shadow-[0_0_8px_rgba(245,158,11,0.2)]";
      default:
        return "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/20";
    }
  };

  const fmtInr = (n: number) =>
    `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;

  return (
    <div className="min-h-screen bg-[#050B14] text-slate-100 overflow-x-hidden selection:bg-brand/30">
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-brand/10 blur-[120px]" />
        <div className="absolute bottom-[-10%] right-[-10%] w-[30%] h-[30%] rounded-full bg-cyan-500/5 blur-[100px]" />
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 relative z-10">
        <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-10 border-b border-white/5 pb-6">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-brand/80 to-brand/20 flex items-center justify-center border border-white/10 shadow-[0_0_20px_rgba(var(--brand-rgb),0.3)]">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                 <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
            </div>
            <div>
              <h1 className="font-display text-2xl font-bold tracking-tight text-white drop-shadow-md">Insurer Command Center</h1>
              <p className="text-xs text-slate-400 mt-1 uppercase tracking-widest font-medium">Portfolio &amp; Forward Risk Analytics</p>
            </div>
          </div>
          <Link to="/login" className="flex items-center gap-2 text-sm text-brand font-semibold hover:text-brand-light transition-colors bg-white/5 px-4 py-2 rounded-lg border border-white/10 hover:bg-white/10 backdrop-blur-md">
            <span>Worker App</span>
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" /></svg>
          </Link>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          
          {/* LEFT SIDEBAR - ACCESS & CONTROLS */}
          <div className="lg:col-span-1 space-y-6">
            <section className={`${shell} p-5`}>
              <div className={innerGlow} />
              <div className="relative z-10">
                <div className="flex items-center gap-2 mb-4">
                  <svg className="w-4 h-4 text-brand" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" /></svg>
                  <h2 className={titleSm}>Access Authentication</h2>
                </div>
                <input
                  type="password"
                  autoComplete="off"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className="w-full rounded-xl bg-black/40 border border-white/10 px-4 py-3 text-white text-sm mb-3 focus:outline-none focus:border-brand/50 focus:ring-1 focus:ring-brand/30 transition-all font-mono"
                  placeholder="Admin Token Payload"
                />
                <button
                  type="button"
                  disabled={loading}
                  onClick={() => void load()}
                  className="w-full rounded-xl bg-brand text-slate-950 font-bold py-3 text-sm disabled:opacity-40 hover:bg-brand-light transition-colors shadow-[0_0_15px_rgba(var(--brand-rgb),0.2)] disabled:shadow-none"
                >
                  {loading ? (
                    <span className="flex items-center justify-center gap-2">
                       <svg className="animate-spin h-4 w-4 text-slate-950" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                       Syncing Cortex...
                    </span>
                  ) : "Load Analytics"}
                </button>
                {err && <p className="text-xs text-rose-300 mt-3 p-2 bg-rose-500/10 rounded-lg border border-rose-500/20">{err}</p>}
                
                <DetailsBlock label="System Configuration">
                  Set <code className="text-brand bg-brand/10 px-1 py-0.5 rounded">ADMIN_ANALYTICS_TOKEN</code> in backend{" "}
                  <code className="text-slate-400 bg-white/5 px-1 py-0.5 rounded">.env</code>. Token is stored locally.
                </DetailsBlock>
              </div>
            </section>

            {/* Fraud Snapshot (if available) moved to sidebar */}
            {fraudSnap && (
              <section className={`${shell} p-5`}>
                 <div className={innerGlow} />
                 <div className="relative z-10">
                   <div className="flex items-center gap-2 mb-4">
                     <svg className="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                     <h2 className={titleSm}>Fraud Watch (30d)</h2>
                   </div>
                   
                   <div className="space-y-3">
                     <div className="p-3 bg-black/30 rounded-xl border border-white/5 flex justify-between items-center">
                       <span className="text-xs text-slate-400">Mean Score (μ)</span>
                       <span className="text-sm text-white font-mono">{String(fraudSnap.mean_fraud_score ?? "—")}</span>
                     </div>
                     <div className="p-3 bg-amber-500/10 rounded-xl border border-amber-500/20 flex justify-between items-center">
                       <span className="text-xs text-amber-200">Review Queue</span>
                       <span className="text-sm font-bold text-amber-400 mr-1 flex items-center gap-1.5">
                         {Number(fraudSnap.claims_pending_fraud_review_gte_075 ?? 0) > 0 && <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />}
                         {String(fraudSnap.claims_pending_fraud_review_gte_075 ?? "0")}
                       </span>
                     </div>
                   </div>
                   <p className="text-[10px] text-slate-500 mt-4 leading-relaxed italic">{String(fraudSnap.note ?? "")}</p>
                 </div>
              </section>
            )}
          </div>

          {/* MAIN DASHBOARD CANVASS */}
          <div className="lg:col-span-3 space-y-6">
            {!portfolio && !loading && !err && (
               <div className="h-full min-h-[400px] flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/20 bg-white/[0.02]">
                 <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mb-4">
                   <svg className="w-8 h-8 text-slate-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z" /></svg>
                 </div>
                 <p className="text-slate-400 font-medium">Awaiting payload. Please authenticate.</p>
               </div>
            )}

            {/* PORTFOLIO METRICS WIDGET */}
            {portfolio && (
              <section className={`${shell} p-6`}>
                <div className={innerGlow} />
                <div className="relative z-10">
                  <div className="flex items-center justify-between mb-5">
                    <h2 className="text-lg font-bold text-white flex items-center gap-2">
                       <svg className="w-5 h-5 text-brand" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                       Portfolio State (Live)
                    </h2>
                    {lossRatio && lossRatio.as_percent != null && (
                      <div className="bg-rose-500/10 border border-rose-500/20 rounded-full px-4 py-1.5 flex items-center gap-2">
                        <span className="w-2 h-2 rounded-full bg-rose-500 shadow-[0_0_8px_#f43f5e]" />
                        <span className="text-xs font-semibold text-rose-200">Loss Ratio 7d: <span className="text-rose-400 font-bold ml-1">{String(lossRatio.as_percent)}%</span></span>
                      </div>
                    )}
                  </div>
                  
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard title="Registered Workers" value={String(portfolio.registered_workers ?? "—")} />
                    <MetricCard title="Active Policies" value={String(portfolio.active_policies ?? "—")} />
                    <MetricCard title="Weekly Premium Pool" value={portfolio.weekly_premium_pool_inr != null ? fmtInr(Number(portfolio.weekly_premium_pool_inr)) : "—"} highlight />
                    <MetricCard title="Paid Claims (7d)" value={portfolio.paid_payouts_last_7d_inr != null ? fmtInr(Number(portfolio.paid_payouts_last_7d_inr)) : "—"} subtext={`${String(portfolio.paid_claim_count_last_7d ?? 0)} paid event(s)`} />
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                    {/* All time stats */}
                    <div className="bg-black/20 rounded-xl p-4 border border-white/5 flex flex-col justify-center">
                       <div className="flex justify-between items-center mb-2 text-xs text-slate-400">
                         <span>All-time Paid Total</span>
                         <span>All-time Loss Ratio</span>
                       </div>
                       <div className="flex justify-between items-end">
                         <span className="text-xl font-bold text-slate-200 tabular-nums">
                            {portfolio.total_paid_payouts_all_time_inr != null ? fmtInr(Number(portfolio.total_paid_payouts_all_time_inr)) : "—"}
                         </span>
                         <span className="text-lg font-bold text-amber-200 tabular-nums">
                            {lossRatioAllTime?.as_percent != null ? `${String(lossRatioAllTime.as_percent)}%` : "—"}
                         </span>
                       </div>
                    </div>
                    
                    {/* Claims by status beautifully mapped */}
                    {portfolio.claims_by_status != null && typeof portfolio.claims_by_status === 'object' && (
                      <div className="bg-black/20 rounded-xl p-4 border border-white/5">
                        <p className="text-xs text-slate-400 mb-3">Claims by Status</p>
                        <div className="flex flex-wrap gap-2">
                          {Object.entries(portfolio.claims_by_status).map(([st, count]) => (
                            <div key={st} className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-white/5 border border-white/10">
                               <span className="text-[10px] uppercase text-slate-400">{st}</span>
                               <span className="text-sm font-bold text-white">{String(count)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </section>
            )}

            {/* PREDICTIVE INSIGHTS WIDGET */}
            {predictionCenter && (
              <section className={`${shell} p-6`}>
                <div className={innerGlow} />
                <div className="relative z-10">
                   <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                     <h2 className="text-lg font-bold text-white flex items-center gap-2">
                        <svg className="w-5 h-5 text-cyan-400" viewBox="0 0 24 24" fill="none" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                        Forward Risk Projection (7d)
                     </h2>
                     {claimForecast && claimForecast.band_next_7d != null && (
                        <div className="flex items-center gap-3">
                           <span className="text-xs text-slate-400">Activity Band:</span>
                           <span className={`px-3 py-1 rounded-md text-xs font-bold uppercase tracking-wider ${
                             String(claimForecast.band_next_7d).toLowerCase() === 'elevated' || String(claimForecast.band_next_7d).toLowerCase() === 'high' ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30' : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/30'
                           }`}>
                             {String(claimForecast.band_next_7d)}
                           </span>
                        </div>
                     )}
                   </div>

                   <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
                      <div className="bg-gradient-to-br from-slate-900/80 to-slate-800/40 p-4 rounded-xl border border-white/10 relative overflow-hidden">
                         <div className="absolute top-0 right-0 w-24 h-24 bg-rose-500/10 blur-2xl rounded-full -mr-4 -mt-4 pointer-events-none" />
                         <p className="text-xs text-slate-400 mb-1">Expected Payout (7d)</p>
                         <p className="text-2xl font-display font-bold text-white">
                           {predictionCenter.illustrative_expected_payout_inr_next_7d != null ? fmtInr(Number(predictionCenter.illustrative_expected_payout_inr_next_7d)) : "—"}
                         </p>
                         {claimForecast?.portfolio_total_new_claim_events != null && (
                           <p className="text-xs text-slate-500 mt-2 font-mono">~{String(claimForecast.portfolio_total_new_claim_events)} predicted events</p>
                         )}
                      </div>
                      <div className="bg-gradient-to-br from-slate-900/80 to-slate-800/40 p-4 rounded-xl border border-white/10">
                         <p className="text-xs text-slate-400 mb-1">Loss / Premium Ratio</p>
                         <p className="text-2xl font-display font-bold text-white">
                           {predictionCenter.illustrative_expected_loss_cost_to_weekly_premium_ratio != null
                            ? `${(Number(predictionCenter.illustrative_expected_loss_cost_to_weekly_premium_ratio) * 100).toFixed(1)}%`
                            : "—"}
                         </p>
                      </div>
                      <div className="bg-gradient-to-br from-slate-900/80 to-brand/10 p-4 rounded-xl border border-brand/20 relative overflow-hidden">
                         <div className="absolute top-0 right-0 w-24 h-24 bg-brand/30 blur-2xl rounded-full -mr-4 -mt-4 pointer-events-none" />
                         <p className="text-xs flex justify-between items-center text-slate-400 mb-1">
                           <span>Capital Buffer (Required)</span>
                           <span className="bg-black/30 px-1.5 py-0.5 rounded text-[10px]">x1.2 Multiplier</span>
                         </p>
                         <p className="text-2xl font-display font-bold text-white tracking-tight">
                           {predictionCenter.illustrative_capital_buffer_inr_next_7d != null ? fmtInr(Number(predictionCenter.illustrative_capital_buffer_inr_next_7d)) : "—"}
                         </p>
                      </div>
                   </div>

                   {/* Watchlist & Risk Index Feeds combined securely */}
                   <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 bg-black/20 p-5 rounded-2xl border border-white/5">
                      {/* Left: Risk Index breakdown */}
                      <div>
                        <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-1.5">
                           <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></svg>
                           Risk Index Modifiers
                        </h3>
                        {weekRollup && (
                           <div className="space-y-2 mb-4">
                              <div className="flex justify-between items-center text-xs">
                                <span className="text-slate-400">Weather Base</span>
                                <span className="font-mono text-white px-2 py-1 bg-white/5 rounded">
                                  {weekRollup.weather_only_mean_pressure_0_1 != null ? String(weekRollup.weather_only_mean_pressure_0_1) : String(weekRollup.worker_weighted_mean_disruption_pressure ?? "—")}
                                </span>
                              </div>
                              <div className="flex justify-between items-center text-xs">
                                <span className="text-slate-400">Social / RSS Overlay</span>
                                <span className="font-mono text-cyan-200 px-2 py-1 bg-cyan-500/10 rounded">
                                  +{String(weekRollup.social_overlay_addition_0_1 ?? "0")}
                                </span>
                              </div>
                              <div className="flex justify-between items-center text-sm pt-2 border-t border-white/10 mt-2">
                                <span className="text-slate-300 font-medium">Combined Pressure</span>
                                <span className="font-mono font-bold text-white drop-shadow-[0_0_8px_rgba(255,255,255,0.4)]">
                                  {String(weekRollup.combined_external_eval_pressure_0_1 ?? "—")}
                                </span>
                              </div>
                           </div>
                        )}
                      </div>

                      {/* Right: RSS Feeds & Peak Days */}
                      <div>
                        {highRiskDays.length > 0 && (
                          <div className="mb-4">
                             <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-3">Peak Stress Dates</h3>
                             <div className="flex flex-wrap gap-2">
                               {highRiskDays.map(d => (
                                 <div key={String(d.date)} className="bg-white/5 rounded-lg border border-white/10 px-2.5 py-1.5 flex flex-col">
                                   <span className="text-xs font-medium text-amber-100">{String(d.date)}</span>
                                   <span className="text-[10px] text-amber-500/80 font-mono mt-0.5">{String(d.max_disruption_pressure_0_1)} · <span className="opacity-70">{String(d.worst_zone_id).split('-')[0]}</span></span>
                                 </div>
                               ))}
                             </div>
                          </div>
                        )}
                        {socialFeed && (
                           <div>
                             <h3 className="text-xs font-semibold text-slate-400 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                               <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9.5a2.5 2.5 0 00-2.5-2.5H14" /></svg>
                               Active RSS Flags
                             </h3>
                             <p className="text-[11px] text-slate-400 mb-1 flex items-center gap-2">
                               <span className={`w-1.5 h-1.5 rounded-full ${String(socialFeed.curfew_social).toLowerCase() === 'true' ? 'bg-rose-500' : 'bg-slate-600'}`} />
                               Curfew: <span className="text-white">{String(socialFeed.curfew_social)}</span>
                             </p>
                             <p className="text-[11px] text-slate-400 flex items-center gap-2">
                               <span className={`w-1.5 h-1.5 rounded-full ${String(socialFeed.traffic_zone_closure).toLowerCase() === 'true' ? 'bg-rose-500' : 'bg-slate-600'}`} />
                               Closure: <span className="text-white">{String(socialFeed.traffic_zone_closure)}</span>
                             </p>
                           </div>
                        )}
                      </div>
                   </div>

                   {/* Watchlist Exposure Table */}
                   {zoneRows.length > 0 && (
                     <div className="mt-8 border outline-none border-white/10 rounded-xl overflow-hidden bg-black/40">
                       <div className="px-4 py-3 border-b border-white/10 bg-white/5 flex items-center justify-between">
                         <h3 className="text-sm font-semibold text-white">Zone Pressure Matrix</h3>
                         {Array.isArray(predictionCenter.stress_watchlist_zone_ids) && (predictionCenter.stress_watchlist_zone_ids as string[]).length > 0 && (
                           <div className="hidden md:flex items-center gap-2 text-[10px] font-mono text-rose-300 bg-rose-500/10 px-2 py-1 rounded">
                             <div className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse" />
                             WATCHLIST: {(predictionCenter.stress_watchlist_zone_ids as string[]).map(z => z.split('-')[0]).join(', ')}
                           </div>
                         )}
                       </div>
                       <div className="overflow-x-auto">
                         <table className="w-full text-left text-sm whitespace-nowrap">
                           <thead>
                             <tr className="bg-white/5 text-[10px] uppercase text-slate-400 tracking-wider">
                               <th className="py-3 px-4 font-semibold w-12 text-center">#</th>
                               <th className="py-3 px-4 font-semibold">Zone Identity</th>
                               <th className="py-3 px-4 font-semibold">Risk Tier</th>
                               <th className="py-3 px-4 text-right font-semibold">Prem Delta</th>
                               <th className="py-3 px-4 text-right font-semibold">Est. Events</th>
                             </tr>
                           </thead>
                           <tbody className="divide-y divide-white/5 text-slate-300">
                             {zoneRows.slice(0, 10).map((z) => (
                               <tr key={String(z.zone_id)} className="hover:bg-white/5 transition-colors group">
                                 <td className="py-3 px-4 text-center text-slate-500 font-mono text-[11px]">{String(z.rank ?? "—")}</td>
                                 <td className="py-3 px-4 font-mono text-[11px] text-white">
                                   <div className="flex items-center gap-2">
                                     {String(z.zone_id)}
                                     {Array.isArray(predictionCenter.stress_watchlist_zone_ids) && (predictionCenter.stress_watchlist_zone_ids as string[]).includes(String(z.zone_id)) && (
                                       <span className="w-1.5 h-1.5 rounded-full bg-rose-500 drop-shadow-[0_0_5px_#f43f5e]" />
                                     )}
                                   </div>
                                 </td>
                                 <td className="py-3 px-4">
                                   <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] font-bold uppercase tracking-wider ${tierBadgeClass(String(z.disruption_risk_tier ?? "low"))}`}>
                                     {String(z.disruption_risk_tier ?? "—")}
                                     <span className="opacity-60">|</span>
                                     <span className="font-mono opacity-100">{String(z.composite_risk_score_0_100 ?? "00")}</span>
                                   </span>
                                 </td>
                                 <td className="py-3 px-4 text-right font-mono text-[11px]">
                                   {z.suggested_weekly_premium_delta_pct != null ? (
                                      <span className={Number(z.suggested_weekly_premium_delta_pct) > 0 ? "text-amber-300" : "text-emerald-300"}>
                                        {Number(z.suggested_weekly_premium_delta_pct) > 0 ? "+" : ""}{String(z.suggested_weekly_premium_delta_pct)}%
                                      </span>
                                   ) : "—"}
                                 </td>
                                 <td className="py-3 px-4 text-right font-mono text-cyan-200/90 group-hover:text-cyan-100 font-bold">
                                   ~{String(z.illustrative_expected_new_claim_events_next_7d ?? "—")}
                                 </td>
                               </tr>
                             ))}
                           </tbody>
                         </table>
                       </div>
                     </div>
                   )}
                </div>
              </section>
            )}

            {/* LOWER GRIDS: Nowcast & Daily Forecasts */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pb-24">
              {nowcast && (
                <section className={`${shell} p-5`}>
                  <div className={innerGlow} />
                  <div className="relative z-10">
                    <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                       <svg className="w-4 h-4 text-brand" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                       Telemetry (24h Snapshot)
                    </h2>
                    {"error" in nowcast && nowcast.error ? (
                      <p className="text-sm text-rose-300 bg-rose-500/10 p-3 rounded-lg border border-rose-500/20">{String(nowcast.error as string)}</p>
                    ) : (
                      <>
                        {nowcastRollup?.summary_line != null && (
                          <p className="text-[12px] text-slate-300 mb-4 bg-white/5 p-2 rounded-lg border border-white/10 font-medium italic">{String(nowcastRollup.summary_line)}</p>
                        )}
                        {nowcastMarkets && nowcastMarkets.length > 0 && (
                          <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
                            {nowcastMarkets.map((m) => (
                              <div key={String(m.zone_id)} className="rounded-xl border border-white/[0.08] bg-black/40 p-3 relative overflow-hidden group">
                                <div className="absolute left-0 top-0 bottom-0 w-1 bg-brand/30 group-hover:bg-brand transition-colors" />
                                <div className="flex justify-between items-center mb-3">
                                   <p className="text-white font-mono text-[11px] truncate">{String(m.zone_id)}</p>
                                   <span className="text-[10px] text-slate-400 bg-white/5 px-1.5 py-0.5 rounded font-mono">pop: {String(m.worker_count ?? 0)}</span>
                                </div>
                                <div className="grid grid-cols-4 gap-2 text-[10px] font-mono text-center">
                                  <div className="bg-white/5 rounded py-1 border border-white/10">
                                    <span className="block text-slate-500">Rain</span>
                                    <span className="text-white">{String(m.forecast_rain_24h_mm ?? "—")}</span>
                                  </div>
                                  <div className="bg-white/5 rounded py-1 border border-white/10">
                                    <span className="block text-slate-500">Max °C</span>
                                    <span className="text-white">{String(m.max_temp_next_24h_c ?? "—")}</span>
                                  </div>
                                  <div className={`rounded py-1 border ${String(m.rain_trigger_now) === 'true' ? 'bg-cyan-500/20 border-cyan-500/30' : 'bg-white/5 border-white/10'}`}>
                                    <span className="block text-slate-500">R.Trig</span>
                                    <span className={String(m.rain_trigger_now) === 'true' ? 'text-cyan-300 font-bold' : 'text-slate-400'}>{String(m.rain_trigger_now ?? "—")}</span>
                                  </div>
                                  <div className={`rounded py-1 border ${String(m.heat_trigger_now) === 'true' ? 'bg-orange-500/20 border-orange-500/30' : 'bg-white/5 border-white/10'}`}>
                                    <span className="block text-slate-500">H.Trig</span>
                                    <span className={String(m.heat_trigger_now) === 'true' ? 'text-orange-300 font-bold' : 'text-slate-400'}>{String(m.heat_trigger_now ?? "—")}</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                </section>
              )}

              {/* Exposure List */}
              {zonesTop && zonesTop.length > 0 && (
                <section className={`${shell} p-5 flex flex-col`}>
                  <div className={innerGlow} />
                  <div className="relative z-10 flex-1 flex flex-col">
                    <h2 className="text-sm font-bold text-white mb-4 flex items-center gap-2">
                       <svg className="w-4 h-4 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                       Geographic Exposure Core
                    </h2>
                    <div className="flex-1 overflow-y-auto pr-2 custom-scrollbar space-y-1.5 max-h-[400px]">
                      {zonesTop.map((z, idx) => (
                        <div key={z.zone_id} className="flex justify-between items-center bg-black/20 hover:bg-white/5 transition-colors border border-white/5 p-2 rounded-lg">
                          <div className="flex items-center gap-2 overflow-hidden">
                             <div className="w-5 text-center text-[10px] text-slate-500 font-mono">{idx + 1}</div>
                             <span className="text-slate-300 font-mono text-[11px] truncate whitespace-nowrap">{z.zone_id}</span>
                          </div>
                          <div className="flex items-center gap-2 shrink-0">
                             <div className="w-16 h-1.5 bg-white/10 rounded-full overflow-hidden hidden sm:block">
                                <div className="h-full bg-emerald-400/80 rounded-full" style={{ width: `${Math.min(100, Math.max(5, (z.workers / (zonesTop[0]?.workers || 1)) * 100))}%` }} />
                             </div>
                             <span className="text-white font-bold font-mono text-[11px] w-8 text-right">{z.workers}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
              )}
            </div>
            
          </div>
        </div>
      </div>
    </div>
  );
}
