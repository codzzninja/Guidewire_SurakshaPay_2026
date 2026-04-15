import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import DashboardSkeleton from "../components/DashboardSkeleton";
import NotificationBell from "../components/NotificationBell";
import { api } from "../lib/api";
import { useAuth } from "../lib/AuthContext";
import { useNotify } from "../lib/useNotify";
import type { Claim, Policy, PremiumQuote } from "../lib/types";
import { WORK_ZONES, zoneById } from "../data/zones";

const PLANS = [
  {
    id: "basic" as const,
    name: "Basic",
    emoji: "🟢",
    blurb: "Part-time, calmer zones",
    base: 20,
    cap: 1000,
    perEvent: 300,
  },
  {
    id: "standard" as const,
    name: "Standard",
    emoji: "🟡",
    blurb: "Regular shifts",
    base: 35,
    cap: 1500,
    perEvent: 500,
  },
  {
    id: "pro" as const,
    name: "Pro",
    emoji: "🔴",
    blurb: "Full-time, higher-risk zones",
    base: 50,
    cap: 2500,
    perEvent: 800,
  },
];

function formatRs(n: number) {
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 0 })}`;
}

/** Poll interval; server caches env data ~5 min — hits are cheap (cache), “Refresh now” forces live APIs. */
const LIVE_POLL_MS = 120_000;

/** Razorpay Test Mode order amount (paise). 10_000 = ₹100 — no real money in test keys. */
const TEST_EARNING_PAISE = 10_000;

function formatTime(d: Date) {
  return d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n));
}

function formatWeekRange(startIso?: string, endIso?: string) {
  if (!startIso || !endIso) return "";
  const s = new Date(startIso);
  const e = new Date(endIso);
  if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return "";
  const sTxt = s.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const eTxt = e.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  return `${sTxt}–${eTxt}`;
}

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms));
}

function toFiniteNumber(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim() !== "") {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

export default function DashboardPage() {
  const { user, logout, refresh } = useAuth();
  const notify = useNotify();
  const [searchParams, setSearchParams] = useSearchParams();
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [live, setLive] = useState<Record<string, unknown> | null>(null);
  const [quote, setQuote] = useState<PremiumQuote | null>(null);
  const [selected, setSelected] = useState<(typeof PLANS)[number]["id"] | null>(
    "standard"
  );
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [evalResult, setEvalResult] = useState<Record<string, unknown> | null>(null);
  const [dailyRows, setDailyRows] = useState<
    { earn_date: string; amount: number; minutes_online?: number | null }[]
  >([]);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState<Date | null>(null);
  const [liveFetching, setLiveFetching] = useState(false);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [workZoneId, setWorkZoneId] = useState(WORK_ZONES[0].id);
  const [stripeReady, setStripeReady] = useState(false);
  const [claimPhase, setClaimPhase] = useState<string | null>(null);
  const [claimPhaseRef, setClaimPhaseRef] = useState<string | null>(null);
  const [claimPhaseStep, setClaimPhaseStep] = useState<0 | 1 | 2 | 3>(0);
  /** Prevents duplicate verify + toasts (Strict Mode / searchParams churn). */
  const stripeReturnHandledRef = useRef<string | null>(null);
  const stripePremiumReturnHandledRef = useRef<string | null>(null);
  const [gpsCapturing, setGpsCapturing] = useState(false);
  const [gpsCaptureProgressMs, setGpsCaptureProgressMs] = useState(0);
  const [pendingGpsSamples, setPendingGpsSamples] = useState<
    {
      lat: number;
      lon: number;
      accuracy?: number;
      speed?: number;
      heading?: number;
      ts: number;
    }[]
  >([]);
  const [workerInsights, setWorkerInsights] = useState<Record<string, unknown> | null>(null);

  const kycOk = user?.kyc_status === "verified";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [p, c, insight] = await Promise.all([
        api<Policy | null>("/policies/active"),
        api<Claim[]>("/claims?limit=5"),
        api<Record<string, unknown>>("/analytics/me").catch(() => null),
      ]);
      setPolicy(p);
      setClaims(c);
      if (insight) setWorkerInsights(insight);
      if (p?.plan_type && ["basic", "standard", "pro"].includes(p.plan_type)) {
        setSelected(p.plan_type as (typeof PLANS)[number]["id"]);
      }
    } catch {
      notify("", "Could not load policy / claims.", "error");
    } finally {
      setLoading(false);
    }
  }, [notify]);

  const refreshDailyEarnings = useCallback(async () => {
    try {
      const rows = await api<
        { earn_date: string; amount: number; minutes_online?: number | null }[]
      >("/users/me/daily-earnings?limit=21");
      setDailyRows(
        [...rows].sort((a, b) => b.earn_date.localeCompare(a.earn_date))
      );
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (loading) return;
    void refreshDailyEarnings();
  }, [loading, refreshDailyEarnings]);

  useEffect(() => {
    if (user?.zone_id && WORK_ZONES.some((z) => z.id === user.zone_id)) {
      setWorkZoneId(user.zone_id);
    }
  }, [user?.zone_id]);

  useEffect(() => {
    void api<{ razorpay_configured?: boolean; stripe_configured?: boolean }>("/health/integrations")
      .then((j) => {
        setStripeReady(Boolean(j.stripe_configured));
      })
      .catch(() => {
        setStripeReady(false);
      });
  }, []);

  const stripeSessionId = searchParams.get("stripe_session_id");
  const stripeCancelled = searchParams.get("stripe_cancelled");
  const stripePremiumSessionId = searchParams.get("stripe_premium_session_id");
  const stripePremiumCancelled = searchParams.get("stripe_premium_cancelled");
  const weeklyPremiumDue = quote?.final_weekly_premium ?? policy?.weekly_premium ?? null;

  useEffect(() => {
    if (loading || !user) return;
    if (stripeCancelled) {
      notify("", "Stripe Checkout cancelled.", "info");
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("stripe_cancelled");
          return next;
        },
        { replace: true },
      );
      return;
    }
    if (!stripeSessionId) return;

    if (stripeReturnHandledRef.current === stripeSessionId) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("stripe_session_id");
          return next;
        },
        { replace: true },
      );
      return;
    }
    stripeReturnHandledRef.current = stripeSessionId;

    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("stripe_session_id");
        return next;
      },
      { replace: true },
    );

    const sid = stripeSessionId;
    void (async () => {
      try {
        const vr = await api<{ credited?: boolean; message?: string; amount_inr?: number }>(
          "/payments/stripe/verify-session",
          {
            method: "POST",
            body: JSON.stringify({ session_id: sid }),
          },
        );
        await refresh();
        await refreshDailyEarnings();
        if (selected) {
          const q = await api<PremiumQuote>("/policies/quote", {
            method: "POST",
            body: JSON.stringify({ plan_type: selected }),
          });
          setQuote(q);
        }
        if (vr.message !== "already_recorded") {
          const amt = vr.amount_inr ?? TEST_EARNING_PAISE / 100;
          notify("Stripe Test payment", `${formatRs(amt)} credited to today`, "success");
        }
      } catch (e) {
        notify("", e instanceof Error ? e.message : "Stripe verify failed", "error");
        stripeReturnHandledRef.current = null;
      }
    })();
  }, [
    loading,
    user,
    stripeSessionId,
    stripeCancelled,
    setSearchParams,
    notify,
    refresh,
    selected,
    refreshDailyEarnings,
  ]);

  useEffect(() => {
    if (loading || !user) return;
    if (stripePremiumCancelled) {
      notify("", "Weekly premium payment cancelled.", "info");
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("stripe_premium_cancelled");
          return next;
        },
        { replace: true },
      );
      return;
    }
    if (!stripePremiumSessionId) return;

    if (stripePremiumReturnHandledRef.current === stripePremiumSessionId) {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          next.delete("stripe_premium_session_id");
          return next;
        },
        { replace: true },
      );
      return;
    }
    stripePremiumReturnHandledRef.current = stripePremiumSessionId;

    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("stripe_premium_session_id");
        return next;
      },
      { replace: true },
    );

    const sid = stripePremiumSessionId;
    void (async () => {
      try {
        const vr = await api<{ message?: string; amount_inr?: number }>(
          "/payments/stripe/verify-premium-session",
          {
            method: "POST",
            body: JSON.stringify({ session_id: sid }),
          },
        );
        await load();
        if (selected) {
          const q = await api<PremiumQuote>("/policies/quote", {
            method: "POST",
            body: JSON.stringify({ plan_type: selected }),
          });
          setQuote(q);
        }
        if (vr.message === "already_activated" || vr.message === "already_paid_this_week") {
          notify("", "Weekly premium already paid for this week.", "info");
        } else {
          notify(
            "Weekly premium paid",
            `${formatRs(vr.amount_inr ?? 0)} received. Coverage is now active.`,
            "success",
          );
        }
      } catch (e) {
        notify("", e instanceof Error ? e.message : "Premium verify failed", "error");
        stripePremiumReturnHandledRef.current = null;
      }
    })();
  }, [
    loading,
    user,
    stripePremiumSessionId,
    stripePremiumCancelled,
    setSearchParams,
    notify,
    selected,
    load,
  ]);

  const refreshLive = useCallback(async (forceRefresh = false) => {
    setLiveFetching(true);
    setLiveError(null);
    try {
      const q = forceRefresh ? "?refresh=true" : "";
      const L = await api<Record<string, unknown>>(`/monitoring/live${q}`);
      setLive(L);
      setLiveUpdatedAt(new Date());
    } catch (e) {
      setLive(null);
      setLiveError(e instanceof Error ? e.message : "Could not load live monitors");
    } finally {
      setLiveFetching(false);
    }
  }, []);

  useEffect(() => {
    if (loading) return;
    void refreshLive();
    const id = setInterval(() => void refreshLive(), LIVE_POLL_MS);
    return () => clearInterval(id);
  }, [loading, refreshLive]);

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === "visible") void refreshLive();
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, [refreshLive]);

  useEffect(() => {
    if (!selected || !user) return;
    let cancelled = false;
    (async () => {
      try {
        const q = await api<PremiumQuote>("/policies/quote", {
          method: "POST",
          body: JSON.stringify({ plan_type: selected }),
        });
        if (!cancelled) setQuote(q);
      } catch {
        if (!cancelled) setQuote(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected, user]);

  async function subscribe() {
    if (!selected) return;
    if (!kycOk) {
      notify(
        "",
        "KYC is required before paying weekly premium. Re-register on a fresh account or add a KYC update API for legacy users.",
        "error"
      );
      return;
    }
    if (!stripeReady) {
      notify("", "Stripe is not configured right now.", "error");
      return;
    }
    setBusy(true);
    try {
      const r = await api<{ url: string }>("/payments/stripe/create-premium-session", {
        method: "POST",
        body: JSON.stringify({ plan_type: selected }),
      });
      window.location.assign(r.url);
    } catch (e) {
      notify("", e instanceof Error ? e.message : "Could not start premium checkout", "error");
      setBusy(false);
    } finally {
      // keep busy=true while browser leaves page; reset only on errors
    }
  }

  async function runEvaluate(
    mock: boolean,
    opts?: { demoWeatherIntegrityMismatch?: boolean }
  ) {
    if (!kycOk) {
      notify(
        "",
        "KYC verification is required before claim payout simulation.",
        "error"
      );
      return;
    }
    setBusy(true);
    setEvalResult(null);
    setClaimPhase("Evaluating disruption...");
    setClaimPhaseRef(null);
    setClaimPhaseStep(1);
    try {
      await sleep(700);
      const r = await api<Record<string, unknown>>("/monitoring/evaluate", {
        method: "POST",
        body: JSON.stringify({
          force_mock_disruption: mock,
          demo_weather_integrity_mismatch: Boolean(opts?.demoWeatherIntegrityMismatch),
        }),
      });
      await sleep(700);
      setClaimPhase("Processing payout via UPI simulator...");
      setClaimPhaseStep(2);
      await sleep(900);
      setEvalResult(r);
      await load();
      await refresh();
      if (r.claim_created) {
        const amt = Number(r.payout_amount);
        const payoutRef =
          typeof r.payout_ref === "string" && r.payout_ref.trim() !== "" ? r.payout_ref : null;
        setClaimPhaseRef(payoutRef);
        setClaimPhase(
          payoutRef ? `Payout success. Ref: ${payoutRef}` : "Payout success via UPI simulator."
        );
        setClaimPhaseStep(3);
        notify(
          "Claim recorded",
          `${formatRs(Number.isFinite(amt) ? amt : 0)} · ${String(r.status)}`,
          "success"
        );
      } else {
        setClaimPhase("Evaluation complete. No payout this run.");
        setClaimPhaseStep(3);
        notify(
          "",
          String(r.message ?? "Evaluation finished — see details below."),
          "info"
        );
      }
    } catch (e) {
      setClaimPhase("Evaluation failed.");
      setClaimPhaseStep(0);
      notify("", e instanceof Error ? e.message : "Evaluation failed", "error");
    } finally {
      window.setTimeout(() => {
        setClaimPhaseStep(0);
      }, 6000);
      setBusy(false);
    }
  }

  async function captureDeviceGps() {
    if (!navigator.geolocation) {
      notify(
        "",
        "Geolocation not available in this browser. Use Chrome/Edge, allow location, or HTTPS.",
        "error"
      );
      return;
    }
    setGpsCapturing(true);
    setGpsCaptureProgressMs(0);
    const samples: {
      lat: number;
      lon: number;
      accuracy?: number;
      speed?: number;
      heading?: number;
      ts: number;
    }[] = [];
    const started = Date.now();
    const duration = 22_000;
    const tick = window.setInterval(() => {
      setGpsCaptureProgressMs(Date.now() - started);
    }, 300);
    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        samples.push({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: pos.coords.accuracy ?? undefined,
          speed: pos.coords.speed ?? undefined,
          heading: pos.coords.heading ?? undefined,
          ts: Date.now(),
        });
      },
      (err: GeolocationPositionError) => {
        clearInterval(tick);
        navigator.geolocation.clearWatch(watchId);
        setGpsCapturing(false);
        const hint =
          err.code === 1
            ? "Location permission denied — open Android Settings → Apps → SurakshaPay → Permissions → Location → Allow."
            : err.code === 3
              ? "GPS timed out — emulator: set a mock location (⋯ Extended controls → Location); real device: go outdoors or enable high accuracy."
              : err.message || "GPS unavailable";
        notify("", hint, "error");
      },
      { enableHighAccuracy: true, maximumAge: 0, timeout: 20_000 }
    );
    await new Promise<void>((r) => setTimeout(r, duration));
    clearInterval(tick);
    navigator.geolocation.clearWatch(watchId);
    setGpsCapturing(false);
    setGpsCaptureProgressMs(0);
    if (samples.length < 3) {
      try {
        const one = await new Promise<{
          lat: number;
          lon: number;
          accuracy?: number;
          speed?: number;
          heading?: number;
          ts: number;
        }>((resolve, reject) => {
          navigator.geolocation.getCurrentPosition(
            (pos) =>
              resolve({
                lat: pos.coords.latitude,
                lon: pos.coords.longitude,
                accuracy: pos.coords.accuracy ?? undefined,
                speed: pos.coords.speed ?? undefined,
                heading: pos.coords.heading ?? undefined,
                ts: Date.now(),
              }),
            reject,
            { enableHighAccuracy: false, maximumAge: 45_000, timeout: 10_000 }
          );
        });
        setPendingGpsSamples([one]);
        notify(
          "GPS fallback captured",
          "Saved a single fix fallback. You can save now (weather will use it).",
          "info"
        );
        return;
      } catch {
        notify(
          "",
          "Not enough GPS fixes — save anyway to use zone center fallback for weather.",
          "error"
        );
        return;
      }
    }
    setPendingGpsSamples(samples);
    notify(
      "Live GPS captured",
      `${samples.length} fixes — save to anchor your real position for fraud checks.`,
      "success"
    );
  }

  async function saveWorkLocation() {
    const z = zoneById(workZoneId) ?? WORK_ZONES[0];
    const trace = pendingGpsSamples;
    const hadTrace = trace.length >= 1;
    setBusy(true);
    try {
      const body: Record<string, unknown> = { zone_id: z.id };
      if (hadTrace) {
        body.gps_attestation = {
          samples: trace,
          source: "device_geolocation",
          captured_at: new Date().toISOString(),
        };
      } else {
        body.lat = z.lat;
        body.lon = z.lon;
      }
      await api("/users/me/profile", {
        method: "PATCH",
        body: JSON.stringify(body),
      });
      await refresh();
      await refreshLive();
      setPendingGpsSamples([]);
      notify(
        "",
        hadTrace
          ? "Work zone + GPS saved."
          : "Work location saved (zone center fallback active for weather).",
        "success"
      );
    } catch (e) {
      notify("", e instanceof Error ? e.message : "Could not update location", "error");
    } finally {
      setBusy(false);
    }
  }

  async function resimulateEarnings() {
    setBusy(true);
    try {
      await api("/users/me/earnings/resimulate", { method: "POST" });
      await refresh();
      await refreshDailyEarnings();
      if (selected) {
        const q = await api<PremiumQuote>("/policies/quote", {
          method: "POST",
          body: JSON.stringify({ plan_type: selected }),
        });
        setQuote(q);
      }
      notify("", "Demo earnings updated for your zone and hours.", "success");
    } catch (e) {
      notify("", e instanceof Error ? e.message : "Could not regenerate earnings", "error");
    } finally {
      setBusy(false);
    }
  }

  const flags = live?.flags as Record<string, boolean> | undefined;
  const liveDetails = live?.details as
    | {
        weather_api?: Record<string, unknown>;
        aqi_api?: Record<string, unknown>;
        rss?: Record<string, unknown>;
      }
    | undefined;
  const wApi = liveDetails?.weather_api;
  const aApi = liveDetails?.aqi_api;

  const rain24Val = toFiniteNumber(wApi?.forecast_rain_24h_mm);
  const tempNowVal = toFiniteNumber(wApi?.temp_c);
  const aqiNowVal = toFiniteNumber(aApi?.aqi_us);
  const rain24 = rain24Val ?? 0;
  const tempNow = tempNowVal ?? 32;
  const aqiNow = aqiNowVal ?? 70;
  const activeFlagCount = flags ? Object.values(flags).filter(Boolean).length : 0;

  // "AI Shift Coach" score (0-100): higher => safer to stay online now.
  const shiftSafetyScore = clamp(
    Math.round(
      100 -
        rain24 * 0.8 -
        Math.max(0, tempNow - 34) * 1.7 -
        Math.max(0, aqiNow - 90) * 0.22 -
        activeFlagCount * 9
    ),
    8,
    95
  );
  const coachTone =
    shiftSafetyScore >= 72 ? "good" : shiftSafetyScore >= 48 ? "watch" : "risk";
  const coachHeadline =
    coachTone === "good"
      ? "High-confidence earning window"
      : coachTone === "watch"
        ? "Caution window — optimize route + breaks"
        : "High disruption risk — keep exposure low";
  const coachAction =
    coachTone === "good"
      ? "Best next 2h: stay active in your primary zone; keep refresh on."
      : coachTone === "watch"
        ? "Best next 2h: prefer short trips, avoid low-visibility stretches."
        : "Best next 2h: pause long routes; re-check in 30-45 minutes.";
  const coachPillClass =
    coachTone === "good"
      ? "bg-emerald-100 text-emerald-900"
      : coachTone === "watch"
        ? "bg-amber-100 text-amber-900"
        : "bg-rose-100 text-rose-900";
  const scoreStroke =
    coachTone === "good" ? "#059669" : coachTone === "watch" ? "#d97706" : "#e11d48";
  const scoreOffset = 251.2 - (251.2 * shiftSafetyScore) / 100; // circumference for r=40
  const currentHour = new Date().getHours();
  const hourRiskBias = (h: number) => {
    if (h >= 12 && h <= 16) return 6; // mid-day heat risk
    if ((h >= 19 && h <= 22) || (h >= 7 && h <= 10)) return -6; // stronger demand windows
    if (h >= 0 && h <= 5) return 8; // late-night risk
    return 0;
  };
  const timeline = Array.from({ length: 6 }, (_, i) => {
    const hour = (currentHour + i) % 24;
    const score = clamp(
      shiftSafetyScore - (i > 2 ? (rain24 > 18 ? 7 : 3) : 0) - hourRiskBias(hour),
      5,
      97
    );
    return {
      hour,
      score,
      label: `${String(hour).padStart(2, "0")}:00`,
      risky: score < 45,
    };
  });
  const bestWindow = timeline.reduce((best, cur) => (cur.score > best.score ? cur : best), timeline[0]);
  const trendDelta = timeline[timeline.length - 1].score - timeline[0].score;
  const trendText =
    trendDelta >= 8
      ? "Risk easing over next hours"
      : trendDelta <= -8
        ? "Risk increasing over next hours"
        : "Risk mostly stable next hours";
  const trendClass =
    trendDelta >= 8 ? "text-emerald-300" : trendDelta <= -8 ? "text-rose-300" : "text-slate-300";
  const sparklinePoints = timeline
    .map((t, i) => {
      const x = 8 + i * 56;
      const y = 84 - (t.score / 100) * 64;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div
      className="min-h-[100dvh] pb-safe safe-pb max-w-lg mx-auto px-4 pt-6 text-slate-100 relative z-10"
      aria-busy={busy}
    >
      <header className="flex items-start justify-between gap-3 mb-6">
        <div>
          <p className="font-display text-2xl font-bold text-white tracking-tight">SurakshaPay</p>
          <p className="text-brand text-sm mt-0.5 font-medium">
            Hi {user?.full_name?.split(" ")[0] ?? "partner"} — food delivery cover
          </p>
        </div>
        <div className="flex items-center gap-1 shrink-0">
          <NotificationBell />
          <Link
            to="/insurer"
            className="text-[11px] font-bold text-slate-400 hover:text-white min-h-[44px] min-w-[44px] px-2 inline-flex items-center justify-center rounded-2xl border border-transparent hover:border-glass-border hover:bg-surface/30 transition-all"
          >
            Insurer
          </Link>
          <button
            type="button"
            onClick={() => {
              logout();
              window.location.href = "/login";
            }}
            className="text-sm text-slate-400 font-bold min-h-[44px] min-w-[44px] px-3 rounded-2xl bg-surface/30 border border-glass-border hover:bg-surface/60 hover:text-white transition-all"
          >
            Log out
          </button>
        </div>
      </header>

      {loading ? (
        <DashboardSkeleton />
      ) : (
        <>
          <section className="glass-card rounded-3xl p-3.5 mb-4 relative overflow-hidden border border-white/10">
            <div className="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-emerald-400 via-brand to-accent" />
            <p className="text-[11px] font-bold text-slate-400 uppercase tracking-widest">
              Worker dashboard — earnings protected &amp; weekly coverage
            </p>
            <div className="mt-2.5 rounded-3xl bg-brand/10 border border-brand/35 p-3.5">
              <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-400">
                This week&apos;s coverage
              </p>
              {policy ? (
                <>
                  <p className="font-display text-2xl font-bold text-white mt-1.5 capitalize">
                    {policy.plan_type} Plan
                  </p>
                  <div className="mt-2 inline-flex items-center rounded-full border border-emerald-400/35 bg-emerald-500/10 px-3 py-1">
                    <span className="text-emerald-300 font-semibold text-sm">
                      Active · {formatRs(policy.weekly_premium)}/week
                    </span>
                  </div>
                  <p className="text-base leading-snug text-slate-300 mt-3">
                    Coverage up to <span className="text-white font-semibold">{formatRs(policy.max_weekly_coverage)}</span>/wk
                    · Max <span className="text-white font-semibold">{formatRs(policy.max_per_event)}</span>/event
                  </p>
                  {formatWeekRange(policy.week_start, policy.week_end) && (
                    <p className="text-xs text-cyan-200/90 mt-2.5">
                      Paid for week: {formatWeekRange(policy.week_start, policy.week_end)}
                    </p>
                  )}
                </>
              ) : (
                <p className="text-warn font-semibold mt-2 bg-warn/10 border border-warn/25 rounded-xl px-3 py-1.5 text-[15px] leading-snug">
                  No active policy — pick a tier below to activate weekly coverage.
                </p>
              )}
              <div className="mt-3 pt-2.5 border-t border-white/10">
                <p className="text-[9px] font-bold uppercase tracking-[0.14em] text-slate-400">Earnings protected</p>
                <p className="font-display text-2xl font-bold text-white mt-1 tabular-nums">
                  {workerInsights
                    ? formatRs(
                        toFiniteNumber(
                          (workerInsights.earnings_protected as Record<string, unknown> | undefined)
                            ?.total_parametric_payouts_inr
                        ) ?? 0
                      )
                    : "…"}
                </p>
              </div>
            </div>
            {workerInsights && (
              <div className="mt-2.5 pt-2.5 border-t border-white/10 grid grid-cols-1 sm:grid-cols-2 gap-1.5 text-sm">
                <div>
                  <span className="text-slate-500">Income baseline (7-day blend)</span>{" "}
                  <span className="text-white font-semibold">
                    {formatRs(
                      toFiniteNumber(
                        (workerInsights.worker as Record<string, unknown> | undefined)?.baseline_daily_inr
                      ) ?? 0
                    )}
                    /day
                  </span>
                </div>
                <div>
                  <span className="text-slate-500">Safe-hour score (now)</span>{" "}
                  <span className="text-emerald-300 font-semibold">
                    {String(
                      (
                        (workerInsights.worker as Record<string, unknown> | undefined)?.safe_hours as
                          | Record<string, unknown>
                          | undefined
                      )?.safe_score_now ?? "—"
                    )}
                  </span>
                </div>
              </div>
            )}
          </section>

          <section className="glass-card rounded-3xl border border-brand/30 p-5 mb-6 relative overflow-hidden bg-gradient-to-br from-brand/10 to-transparent">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-wide text-slate-300 font-semibold">
                  AI Shift Coach
                </p>
                <h2 className="font-display text-lg leading-tight mt-1">{coachHeadline}</h2>
                <p className="text-xs text-slate-300 mt-1.5 leading-relaxed">{coachAction}</p>
              </div>
              <div className="relative h-24 w-24 shrink-0">
                <svg viewBox="0 0 100 100" className="h-24 w-24">
                  <circle cx="50" cy="50" r="40" stroke="rgba(148,163,184,0.25)" strokeWidth="8" fill="none" />
                  <circle
                    cx="50"
                    cy="50"
                    r="40"
                    stroke={scoreStroke}
                    strokeWidth="8"
                    fill="none"
                    strokeLinecap="round"
                    transform="rotate(-90 50 50)"
                    strokeDasharray="251.2"
                    strokeDashoffset={scoreOffset}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="font-display text-xl font-bold">{shiftSafetyScore}</span>
                  <span className="text-[10px] text-slate-300">/ 100</span>
                </div>
              </div>
            </div>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <span className={`text-[11px] px-2 py-1 rounded-full font-medium ${coachPillClass}`}>
                {coachTone === "good"
                  ? "Suggested mode: Aggressive earnings"
                  : coachTone === "watch"
                    ? "Suggested mode: Balanced safety"
                    : "Suggested mode: Capital protection"}
              </span>
              <span className="text-[11px] text-slate-300">
                Policy: {policy ? `${policy.plan_type} active` : "No active coverage"}
              </span>
            </div>
            <div className="mt-3 rounded-xl bg-white/5 border border-white/10 p-3">
              <div className="flex items-center justify-between gap-2 mb-2">
                <p className="text-[11px] uppercase tracking-wide text-slate-300 font-semibold">
                  Next 6h risk timeline
                </p>
                <p className={`text-[11px] font-medium ${trendClass}`}>{trendText}</p>
              </div>
              <svg viewBox="0 0 300 92" className="w-full h-20">
                <polyline
                  points={sparklinePoints}
                  fill="none"
                  stroke="rgba(148,163,184,0.35)"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <polyline
                  points={sparklinePoints}
                  fill="none"
                  stroke={scoreStroke}
                  strokeWidth="3"
                  strokeLinecap="round"
                />
                {timeline.map((t, i) => {
                  const cx = 8 + i * 56;
                  const cy = 84 - (t.score / 100) * 64;
                  return (
                    <circle
                      key={t.label}
                      cx={cx}
                      cy={cy}
                      r="3.6"
                      fill={t.risky ? "#fb7185" : scoreStroke}
                    />
                  );
                })}
              </svg>
              <div className="mt-1 grid grid-cols-6 gap-1 text-[10px] text-slate-300">
                {timeline.map((t) => (
                  <div key={t.label} className="text-center">
                    <p>{t.label}</p>
                    <p className={t.risky ? "text-rose-300 font-medium" : ""}>{t.score}</p>
                  </div>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-slate-200">
                Best window: <span className="font-semibold">{bestWindow.label}</span> (score {bestWindow.score})
              </p>
            </div>
          </section>

          <section className="mb-6">
            <h2 className="font-display text-xl font-bold text-white mb-4 tracking-tight">Weekly coverage tiers</h2>
            <div className="space-y-2">
              {PLANS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => setSelected(p.id)}
                  className={`w-full text-left rounded-2xl border p-5 transition-all ${
                    selected === p.id
                      ? "border-brand bg-brand/10 shadow-glow ring-1 ring-brand/30"
                      : "border-glass-border bg-surface/30 hover:bg-surface/50"
                  }`}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-bold text-white text-lg">
                      {p.emoji} {p.name}
                    </span>
                    <span className="text-slate-400 text-sm font-medium">
                      from {formatRs(p.base)}/wk
                    </span>
                  </div>
                  <p className="text-sm text-slate-400 mt-1.5">{p.blurb}</p>
                </button>
              ))}
            </div>
            {quote && (
              <div className="mt-4 rounded-3xl bg-surface/40 border border-brand/20 backdrop-blur-md p-6 shadow-[inset_0_0_20px_rgba(56,189,248,0.05)] animate-slide-up relative overflow-hidden">
                <div className="absolute top-0 right-0 w-32 h-32 bg-brand/10 blur-[50px] rounded-full" />
                <p className="text-[11px] uppercase tracking-widest text-brand font-bold">
                  AI-Adjusted Premium
                </p>
                <p className="text-xs text-slate-400 mt-1 capitalize">
                  Quote for: <span className="text-slate-200">{selected}</span> tier
                  {policy && policy.plan_type !== selected ? (
                    <span className="text-amber-300">
                      {" "}
                      (active plan is {policy.plan_type} — tap a tier to compare)
                    </span>
                  ) : null}
                </p>
                <p className="font-display text-3xl font-bold mt-2 text-white">
                  {formatRs(quote.final_weekly_premium)}
                  <span className="text-lg font-medium text-slate-400"> / week</span>
                </p>
                <p className="text-sm text-slate-300 mt-2">
                  Base {formatRs(quote.base_weekly_premium)} + ML risk{" "}
                  {quote.ml_risk_adjustment >= 0 ? "+" : ""}
                  {formatRs(quote.ml_risk_adjustment)}
                  {quote.zone_safety_premium_credit !== 0 ? (
                    <span className="text-emerald-300">
                      {" "}
                      · zone safety {formatRs(quote.zone_safety_premium_credit)}
                    </span>
                  ) : null}{" "}
                  → total adj.{" "}
                  {quote.risk_adjustment >= 0 ? "+" : ""}
                  {formatRs(quote.risk_adjustment)}
                </p>
                {typeof quote.dynamic_coverage?.extra_coverage_hours === "number" &&
                quote.dynamic_coverage.extra_coverage_hours > 0 ? (
                  <p className="text-xs text-amber-200 mt-2 leading-relaxed">
                    Predictive weather: +{String(quote.dynamic_coverage.extra_coverage_hours)}h
                    coverage window · caps {formatRs(quote.max_per_event)} / event
                  </p>
                ) : (
                  <p className="text-xs text-slate-500 mt-2 leading-relaxed">
                    {String(quote.dynamic_coverage?.rationale ?? "")}
                  </p>
                )}
                <details className="mt-3 text-xs text-slate-400">
                  <summary className="cursor-pointer">ML explainability &amp; features</summary>
                  <p className="mt-2 text-slate-500">
                    {String(
                      (quote.pricing_explainability as { explainability_note?: string })
                        ?.explainability_note ?? ""
                    )}
                  </p>
                  <pre className="mt-2 whitespace-pre-wrap break-all overflow-x-auto">
                    {JSON.stringify(quote.pricing_explainability, null, 2)}
                  </pre>
                  <pre className="mt-2 whitespace-pre-wrap break-all overflow-x-auto text-slate-500">
                    {JSON.stringify(quote.feature_snapshot, null, 2)}
                  </pre>
                </details>
              </div>
            )}
            {policy ? (
              <p className="mt-4 text-sm text-slate-600 text-center">
                You already have an active plan for this calendar week. Premium quotes
                refresh when you change zone/hours or regenerate demo earnings.
              </p>
            ) : (
              <>
                <button
                  type="button"
                  disabled={busy || !selected || !stripeReady}
                  onClick={subscribe}
                  className="w-full mt-6 rounded-2xl bg-gradient-to-r from-accent to-brand text-white font-bold text-base py-4 shadow-glow disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98] transition-all"
                >
                  Pay Weekly Premium &amp; Activate
                </button>
                {!stripeReady && (
                  <p className="mt-2 text-xs text-amber-300">
                    Stripe is not configured. Add `STRIPE_SECRET_KEY` in backend `.env`.
                  </p>
                )}
              </>
            )}
          </section>

          <section className="glass-card rounded-3xl p-5 mb-6">
            <h2 className="font-display font-bold text-lg text-white mb-1 tracking-tight">Work Area (GPS)</h2>
            <p className="text-sm text-slate-400 mb-4 leading-relaxed">
              Pick your delivery hub, then use <strong className="text-slate-200">real device GPS</strong> so
              payouts can run fraud checks (zone match + MSTS anti-spoofing).
            </p>
            <select
              className="w-full rounded-2xl border border-glass-border bg-surface/50 text-white px-4 py-3.5 outline-none focus:ring-2 focus:ring-brand/50 mb-3 font-medium transition-all"
              value={workZoneId}
              onChange={(e) => setWorkZoneId(e.target.value)}
            >
              {WORK_ZONES.map((z) => (
                <option key={z.id} value={z.id}>
                  {z.label}
                </option>
              ))}
            </select>
            <p className="text-[11px] text-slate-400 font-mono mb-3">
              Zone center: {(zoneById(workZoneId) ?? WORK_ZONES[0]).lat.toFixed(4)}°,{" "}
              {(zoneById(workZoneId) ?? WORK_ZONES[0]).lon.toFixed(4)}°
            </p>
            {user?.gps_sample_count != null && user.gps_sample_count > 0 ? (
              <p className="text-[11px] text-emerald-600 mb-2">
                On file: {user.gps_sample_count} GPS fixes
                {user.gps_captured_at
                  ? ` · ${new Date(user.gps_captured_at).toLocaleString()}`
                  : ""}
              </p>
            ) : (
              <p className="text-[11px] text-amber-700/90 mb-2">
                No live GPS trace yet — capture below so Isolation Forest + MSTS are fully informed.
              </p>
            )}
            {pendingGpsSamples.length > 0 && (
              <p className="text-[11px] text-brand font-semibold mb-2">
                Ready to save: {pendingGpsSamples.length} fixes buffered
              </p>
            )}
            {gpsCapturing && (
              <p className="text-xs text-brand mb-2 animate-pulse">
                Scanning GPS… {Math.round(gpsCaptureProgressMs / 1000)}s / 22s — keep the app open
              </p>
            )}
            <div className="flex flex-col gap-2">
              <button
                type="button"
                disabled={busy || gpsCapturing}
                onClick={() => void captureDeviceGps()}
                className="w-full rounded-2xl border border-brand/40 bg-brand/10 text-white font-semibold py-3.5 disabled:opacity-50 hover:bg-brand/20 transition-all"
              >
                {gpsCapturing ? "Capturing live GPS…" : "Capture live GPS (~22s)"}
              </button>
              <button
                type="button"
                disabled={busy || gpsCapturing}
                onClick={() => void saveWorkLocation()}
                className="w-full rounded-2xl bg-gradient-to-r from-accent/90 to-brand text-white font-bold py-3.5 disabled:opacity-50 shadow-glow hover:scale-[1.01] active:scale-[0.99] transition-all"
              >
                Save work location
              </button>
            </div>
          </section>

          <section className="glass-card rounded-3xl p-5 mb-6">
            <div className="flex justify-between items-center mb-3 gap-2">
              <div>
                <h2 className="font-display font-bold text-lg text-white tracking-tight">Active Monitors</h2>
                <p className="text-[11px] font-bold tracking-widest mt-1 flex items-center gap-1.5 flex-wrap">
                  <span
                    className={`inline-flex items-center gap-1 ${liveFetching ? "text-brand" : "text-emerald-700"}`}
                  >
                    <span
                      className={`h-2 w-2 rounded-full ${liveFetching ? "bg-brand animate-pulse" : "bg-emerald-500"}`}
                    />
                    {liveFetching
                      ? "Fetching OpenWeather + WAQI + RSS…"
                      : "Auto-refresh every 2 min + when you return to this tab"}
                  </span>
                </p>
                {liveUpdatedAt && (
                  <p className="text-[11px] text-slate-400 mt-1">
                    Last UI pull: {formatTime(liveUpdatedAt)}
                  </p>
                )}
                {live &&
                typeof live.data_freshness === "object" &&
                live.data_freshness !== null ? (
                  <p className="text-[11px] text-emerald-700/90 mt-1 font-mono">
                    Snapshot:{" "}
                    {String(
                      (live.data_freshness as { fetched_at?: string }).fetched_at ?? "—"
                    )}
                    {" · "}
                    age{" "}
                    {(live.data_freshness as { age_seconds?: number }).age_seconds ?? "—"}s
                    {(live.data_freshness as { cache_hit?: boolean }).cache_hit
                      ? " · served from cache"
                      : " · fresh fetch"}
                    {(live.data_freshness as { stale_fallback?: boolean }).stale_fallback
                      ? " (stale — APIs failed)"
                      : ""}
                  </p>
                ) : null}
              </div>
              <button
                type="button"
                disabled={liveFetching}
                onClick={() => void refreshLive(true)}
                className="text-sm text-brand font-medium shrink-0 disabled:opacity-50"
              >
                Refresh now
              </button>
            </div>
            <p className="text-xs text-slate-500 mb-3">
              Weather/AQI/RSS are cached server-side (TTL ~5 min); auto-refresh uses cache when
              fresh. &quot;Refresh now&quot; bypasses cache and pulls live APIs.
            </p>
            {liveError && (
              <p className="text-sm text-red-600 bg-red-50 rounded-lg px-3 py-2 mb-3">
                {liveError}
              </p>
            )}
            {wApi && (
              <div className="grid grid-cols-2 gap-2 mb-3 text-xs">
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-slate-500">Temp (now)</p>
                  <p className="font-semibold text-slate-900">
                    {tempNowVal !== null ? `${tempNowVal.toFixed(2)}°C` : "N/A"}
                  </p>
                  <p className="text-slate-400 mt-0.5">
                    src: {String(wApi.source ?? "—")}
                  </p>
                </div>
                <div className="rounded-lg bg-slate-50 px-3 py-2">
                  <p className="text-slate-500">Rain (24h fcst)</p>
                  <p className="font-semibold text-slate-900">
                    {rain24Val !== null ? `${rain24Val.toFixed(2)} mm` : "N/A"}
                  </p>
                </div>
              </div>
            )}
            {aApi && (
              <div className="rounded-lg bg-slate-50 px-3 py-2 mb-3 text-xs">
                <span className="text-slate-500">Air quality </span>
                {aApi.source === "waqi_no_station" ? (
                  <span className="text-slate-600">
                    No WAQI station — using OpenWeather air pollution if available on refresh
                  </span>
                ) : (
                  <>
                    <span className="font-semibold text-slate-900">
                      {aqiNowVal !== null ? `~${Math.round(aqiNowVal)} US AQI scale` : "N/A"}
                    </span>
                    <span className="text-slate-400">
                      {" "}
                      · {String(aApi.source ?? "")}
                    </span>
                  </>
                )}
              </div>
            )}
            {!live && !liveError && !liveFetching ? (
              <p className="text-sm text-slate-500">Waiting for first live pull…</p>
            ) : live ? (
              <div className="flex flex-wrap gap-2">
                {flags &&
                  Object.entries(flags).map(([k, v]) => (
                    <span
                      key={k}
                      className={`text-xs px-2 py-1 rounded-full ${
                        v ? "bg-amber-100 text-amber-900" : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {k.replace(/_/g, " ")}: {v ? "on" : "off"}
                    </span>
                  ))}
              </div>
            ) : null}
          </section>

          <section className="glass-card rounded-3xl border border-dashed border-brand/30 bg-brand/5 p-5 mb-6">
            <h2 className="font-display font-bold text-xl text-white tracking-tight">Zero-Touch Claim Demo</h2>
            <p className="text-sm text-slate-400 mt-2 leading-relaxed">
              Dual-gate check: external disruption + your income drop vs baseline.
            </p>
            <div className="flex flex-col gap-2 mt-4">
              <button
                type="button"
                disabled={busy || !kycOk}
                onClick={() => void runEvaluate(true)}
                className="rounded-2xl bg-gradient-to-r from-brand to-brand2 shadow-glow text-white font-bold py-4 disabled:opacity-50 hover:scale-[1.02] active:scale-[0.98] transition-all"
              >
                Simulate Disruption (Guaranteed demo)
              </button>
              <button
                type="button"
                disabled={busy || !kycOk}
                onClick={() => void runEvaluate(false)}
                className="rounded-2xl bg-surface/50 border border-glass-border text-white font-bold py-4 disabled:opacity-50 hover:bg-surface/80 transition-all font-medium"
              >
                Run Live APIs Only
              </button>
              <button
                type="button"
                disabled={busy || !kycOk}
                onClick={() => void runEvaluate(false, { demoWeatherIntegrityMismatch: true })}
                className="rounded-2xl bg-amber-950/40 border border-amber-500/40 text-amber-100 font-semibold py-3 px-4 text-sm disabled:opacity-50 hover:bg-amber-950/60 transition-all"
              >
                Weather fraud edge (flag vs metrics)
              </button>
              <p className="text-[11px] text-slate-500 leading-relaxed">
                Third button uses the <span className="text-slate-400">live</span> path and asks the API to inject
                contradictory rain flags vs raw mm/h (needs{" "}
                <code className="text-slate-400">DEMO_WEATHER_EDGE_CASE=true</code> or{" "}
                <code className="text-slate-400">ALLOW_MOCKS=true</code>). When injected, a{" "}
                <span className="text-slate-400">standalone weather-edge gate</span> runs: flag-vs-metrics or weak rain
                vs history → <span className="text-slate-400">claim rejected</span> (not blended with the GPS/IF fraud
                score). Guaranteed demo is unchanged.
              </p>
            </div>
            {claimPhase && (
              <div className="mt-3 rounded-xl border border-cyan-300/30 bg-cyan-950/20 px-3 py-2">
                <div className="space-y-1.5 text-[11px]">
                  <p className={claimPhaseStep >= 1 ? "text-cyan-100" : "text-slate-500"}>
                    {claimPhaseStep >= 1 ? "✓ " : "• "}Evaluating disruption...
                  </p>
                  <p className={claimPhaseStep >= 2 ? "text-cyan-100" : "text-slate-500"}>
                    {claimPhaseStep >= 2 ? "✓ " : "• "}Processing payout via UPI simulator...
                  </p>
                  <p className={claimPhaseStep >= 3 ? "text-cyan-100" : "text-slate-500"}>
                    {claimPhaseStep >= 3 ? "✓ " : "• "}Payout success
                  </p>
                </div>
                <p className="text-xs text-cyan-100 mt-2">{claimPhase}</p>
                {claimPhaseRef && (
                  <p className="text-[11px] text-cyan-300/90 font-mono mt-1 break-all">{claimPhaseRef}</p>
                )}
              </div>
            )}
            {evalResult && (
              <div className="mt-4 space-y-3">
                {typeof evalResult.demo_weather_integrity_hint === "string" &&
                  evalResult.demo_weather_integrity_hint.trim() !== "" && (
                    <div className="rounded-xl border border-slate-500/40 bg-slate-900/40 px-3 py-2 text-[11px] text-slate-300">
                      {evalResult.demo_weather_integrity_hint}
                    </div>
                  )}
                {(evalResult.fraud_score != null ||
                  (typeof evalResult.fraud_notes === "string" && evalResult.fraud_notes.length > 0)) && (
                  <div className="rounded-2xl border border-amber-200/35 bg-amber-950/25 p-4">
                    <p className="text-[10px] font-bold uppercase tracking-widest text-amber-200/90 mb-2">
                      Fraud score &amp; notes
                    </p>
                    <p className="text-2xl font-display font-bold text-white tabular-nums">
                      {evalResult.fraud_score != null ? Number(evalResult.fraud_score).toFixed(3) : "—"}
                      <span className="text-sm font-normal text-slate-400 ml-2">0–1 (higher = riskier)</span>
                    </p>
                    {typeof evalResult.fraud_notes === "string" && evalResult.fraud_notes.trim() !== "" && (
                      <p className="text-xs text-amber-100/90 mt-3 leading-relaxed whitespace-pre-wrap border-t border-white/10 pt-3">
                        {evalResult.fraud_notes}
                      </p>
                    )}
                    <p className="text-[10px] text-slate-500 mt-2 leading-relaxed">
                      Includes GPS/zone, velocity, weather-flag consistency,{" "}
                      <strong className="text-slate-400">rolling weather history</strong> vs current claim, peer
                      earnings, and model score. Notes mention which checks fired.
                    </p>
                  </div>
                )}
                {typeof evalResult.fraud_msts === "object" &&
                  evalResult.fraud_msts !== null && (
                    <div className="rounded-2xl border border-emerald-200/40 bg-emerald-950/30 p-4">
                      <p className="text-[10px] font-bold uppercase tracking-widest text-emerald-400/90 mb-2">
                        Fraud &amp; MSTS (signals)
                      </p>
                      <dl className="grid grid-cols-2 gap-x-2 gap-y-1 text-[11px] text-slate-300">
                        {Object.entries(evalResult.fraud_msts as Record<string, unknown>).map(
                          ([k, v]) => (
                            <div key={k} className="contents">
                              <dt className="text-slate-500 font-mono truncate">{k}</dt>
                              <dd className="text-white font-medium text-right">
                                {typeof v === "number" ? v.toFixed(4) : String(v)}
                              </dd>
                            </div>
                          )
                        )}
                      </dl>
                    </div>
                  )}
                <details className="text-xs">
                  <summary className="cursor-pointer text-slate-500 hover:text-slate-300">Raw evaluate response</summary>
                  <pre className="mt-2 bg-white/80 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap text-slate-800">
                    {JSON.stringify(evalResult, null, 2)}
                  </pre>
                </details>
              </div>
            )}
          </section>

          <section className="mb-6">
            <h2 className="font-display font-bold text-xl text-white tracking-tight mb-4">Claims</h2>
            {claims.length === 0 ? (
              <div className="rounded-3xl border border-dashed border-glass-border bg-surface/30 px-5 py-8 text-center">
                <p className="text-slate-300 text-sm font-bold tracking-wide uppercase">No claims yet</p>
                <p className="text-slate-400 text-xs mt-2.5 leading-relaxed max-w-[80%] mx-auto">
                  When a covered disruption hits and the dual-gate passes, payouts show up here
                  automatically.
                </p>
              </div>
            ) : (
              <ul className="space-y-2">
                {claims.map((c) => (
                  <li
                    key={c.id}
                    className="rounded-2xl bg-surface/40 border border-glass-border p-4 text-sm hover:border-brand/30 transition-colors"
                  >
                    <div className="flex justify-between items-center gap-2">
                      <span className="font-bold text-white text-lg">{formatRs(c.payout_amount)}</span>
                      <span
                        className={
                          c.status === "paid"
                            ? "text-emerald-700"
                            : c.status === "rejected"
                              ? "text-red-600"
                              : "text-amber-700"
                        }
                      >
                        {c.status}
                      </span>
                    </div>
                    <p className="text-slate-500 text-xs mt-1">{c.disruption_type}</p>
                    {c.premium_paid_amount > 0 ? (
                      <p className="text-[11px] text-slate-400 mt-1">
                        Weekly premium paid: {formatRs(c.premium_paid_amount)}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="glass-card rounded-3xl p-5 mb-8">
            <h2 className="font-display font-bold text-lg text-white mb-2 tracking-tight">
              Daily earnings baseline
            </h2>
            <p className="text-xs text-slate-400 mb-4 leading-relaxed">
              Amounts start as <strong>model-generated</strong> (zone + hours). Coverage now activates only
              after <strong>weekly premium payment</strong> through Stripe. Baseline blends{" "}
              <strong>same weekday median</strong> + <strong>7-day MA</strong>.
            </p>
            <div className="mb-3 rounded-xl border border-indigo-300/50 bg-indigo-950/40 px-3 py-2">
              <p className="text-xs text-indigo-100 font-medium">Weekly premium for this week</p>
              <p className="text-[11px] text-indigo-200/90 mt-1">
                {weeklyPremiumDue != null
                  ? `Amount due: ${formatRs(weeklyPremiumDue)}`
                  : "Select a plan to see your premium amount."}
              </p>
              {policy && formatWeekRange(policy.week_start, policy.week_end) && (
                <p className="text-[11px] text-cyan-200/90 mt-1">
                  Paid for week: {formatWeekRange(policy.week_start, policy.week_end)}
                </p>
              )}
              {!policy && (
                <button
                  type="button"
                  disabled={
                    busy || !selected || !stripeReady || weeklyPremiumDue == null || !kycOk
                  }
                  onClick={subscribe}
                  className="mt-2 w-full rounded-lg bg-indigo-600 text-white text-sm font-semibold py-2.5 disabled:opacity-50"
                >
                  Pay {formatRs(weeklyPremiumDue ?? 0)} weekly premium
                </button>
              )}
              {!policy && !kycOk ? (
                <p className="text-[11px] text-amber-200/90 mt-2">
                  KYC not verified on this account — complete registration with PAN/Aadhaar tail on a new
                  user, or wire a profile KYC update.
                </p>
              ) : null}
            </div>
            <div className="max-h-56 overflow-y-auto space-y-2 mb-4 rounded-xl border border-glass-border bg-surface/30 p-3">
              {dailyRows.length === 0 ? (
                <p className="text-xs text-slate-400 py-3 text-center">Loading history…</p>
              ) : (
                dailyRows.map((r) => (
                  <div
                    key={r.earn_date}
                    className="flex justify-between items-center text-sm gap-2 px-2 py-1.5 border-b border-glass-border/50 last:border-0"
                  >
                    <span className="text-slate-400 font-mono text-xs shrink-0">
                      {r.earn_date}
                    </span>
                    <span className="font-bold text-white">{formatRs(r.amount)}</span>
                  </div>
                ))
              )}
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => void resimulateEarnings()}
              className="text-sm font-bold text-brand hover:text-brand2 transition-colors w-full text-center pb-2"
            >
              Regenerate demo earnings
            </button>
          </section>

          <p className="text-center text-xs text-slate-400 pb-4">
            Install this app: use your browser &quot;Add to Home Screen&quot; (PWA).
          </p>
          <p className="text-center text-xs pb-6">
            <Link to="/login" className="text-brand">
              Switch account
            </Link>
          </p>
        </>
      )}
    </div>
  );
}
