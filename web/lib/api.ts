// Typed client for the Python FastAPI backend (proxied via next.config rewrites).

export interface Bias {
  overall?: string;
  monthly?: string;
  weekly?: string;
  daily?: string;
  synchronized?: boolean;
}

export interface Status {
  price: number | null;
  quarter: string | null;
  in_session: boolean | null;
  next_poll: string | null;
  macro_bias: string | null;
  micro_bias: string | null;
  bias: Bias;
  engine: string;
  mode: string;
  health: string;
  levels: Record<string, number | string>;
  volume_profile: Record<string, number>;
  last_signal: Record<string, unknown> | null;
}

export interface BotConfig {
  risk_pct: number;
  sl_buffer: number;
  min_rr: number;
  tp1_rr: number;
  strategy_enabled: boolean;
  daily_report_enabled: boolean;
}

export async function getStatus(): Promise<Status> {
  const r = await fetch("/api/status", { cache: "no-store" });
  if (!r.ok) throw new Error(`status HTTP ${r.status}`);
  return r.json();
}

export async function getConfig(): Promise<BotConfig> {
  const r = await fetch("/api/config", { cache: "no-store" });
  if (!r.ok) throw new Error(`config HTTP ${r.status}`);
  return r.json();
}

export async function postConfig(patch: Partial<BotConfig>): Promise<BotConfig> {
  const r = await fetch("/api/config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
  if (!r.ok) throw new Error(`config POST HTTP ${r.status}`);
  return r.json();
}

// --- MT5 live session (real money) ---------------------------------------
// connect ARMS live trading; disconnect DISARMS. Both are token-gated by the
// backend (DASHBOARD_TOKEN). The password is sent once and never stored client
// side. The token rides as a query param so the next.config proxy forwards it.

export interface Mt5Account {
  login?: number;
  server?: string;
  balance?: number;
  currency?: string;
  name?: string;
}

export interface Mt5Status {
  status?: string;        // "connected" | "error" (connect) — absent on disconnect
  connected?: boolean;    // present on disconnect status dict
  mode?: string;          // "disconnected" | "feed" | "armed"
  login?: number | null;
  server?: string | null;
  account?: Mt5Account | null;
  live_armed?: boolean;
  reason?: string;        // present on error
  code?: number;
}

async function postMt5(path: string, token: string, body?: unknown): Promise<Mt5Status> {
  const r = await fetch(`/api/${path}?token=${encodeURIComponent(token)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = (await r.json().catch(() => ({}))) as Mt5Status;
  if (!r.ok) throw new Error(data.reason || data.status || `HTTP ${r.status}`);
  return data;
}

export function connectMt5(
  login: number, password: string, server: string, token: string
): Promise<Mt5Status> {
  return postMt5("connect-mt5", token, { login, password, server });
}

export function disconnectMt5(token: string): Promise<Mt5Status> {
  return postMt5("disconnect-mt5", token);
}
