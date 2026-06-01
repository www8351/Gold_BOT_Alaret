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
