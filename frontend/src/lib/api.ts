import { Capacitor } from "@capacitor/core";

const nativeDefaultBase = "http://10.0.2.2:8000";
const BASE =
  import.meta.env.VITE_API_BASE ||
  (Capacitor.isNativePlatform() ? nativeDefaultBase : "/api");

function headers(): HeadersInit {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const t = localStorage.getItem("sp_token");
  if (t) h["Authorization"] = `Bearer ${t}`;
  return h;
}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const r = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { ...headers(), ...(opts.headers || {}) },
  });
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = j.detail.map((x: { msg?: string }) => x.msg || "").join(", ");
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  if (r.status === 204) return undefined as T;
  return r.json() as Promise<T>;
}

/** Insurer / admin analytics (`GET /analytics/admin/summary`). */
export async function apiAdmin<T>(
  path: string,
  adminToken: string,
  opts: RequestInit = {}
): Promise<T> {
  const h: Record<string, string> = {
    "Content-Type": "application/json",
    "X-Suraksha-Admin-Token": adminToken,
  };
  const r = await fetch(`${BASE}${path}`, {
    ...opts,
    headers: { ...h, ...(opts.headers || {}) },
  });
  if (!r.ok) {
    let msg = r.statusText;
    try {
      const j = await r.json();
      if (typeof j.detail === "string") msg = j.detail;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return r.json() as Promise<T>;
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("sp_token", token);
  else localStorage.removeItem("sp_token");
}

export function getToken() {
  return localStorage.getItem("sp_token");
}
