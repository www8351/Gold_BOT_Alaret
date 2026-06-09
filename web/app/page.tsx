"use client";

import { useEffect, useState, useCallback } from "react";
import { Activity, Gauge, Radio, Target, Wifi, WifiOff, ShieldAlert, Power } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import {
  getStatus, getConfig, postConfig, connectMt5, disconnectMt5,
  type Status, type BotConfig, type Mt5Status,
} from "@/lib/api";

const REFRESH = 5000;
const fmt = (v: unknown) => (typeof v === "number" ? v.toFixed(2) : (v ?? "—") as string);

function Row({ k, v, accent }: { k: string; v: React.ReactNode; accent?: string }) {
  return (
    <div className="flex justify-between border-b border-border py-1.5 last:border-0">
      <span className="text-muted-foreground">{k}</span>
      <span className={accent}>{v}</span>
    </div>
  );
}

function biasColor(b?: string | null) {
  return b === "bullish" ? "text-up" : b === "bearish" ? "text-down" : "text-muted-foreground";
}

// Numeric config fields the user can edit. risk_pct is stored as a fraction
// (0.01) but edited as a percent (1.00); the rest map 1:1.
type NumKey = "risk_pct" | "sl_buffer" | "min_rr" | "tp1_rr";
const NUM_FIELDS: { key: NumKey; label: string; asPercent?: boolean; prefix?: string }[] = [
  { key: "risk_pct", label: "Risk %", asPercent: true },
  { key: "sl_buffer", label: "SL buffer" },
  { key: "min_rr", label: "Min R:R", prefix: "1:" },
  { key: "tp1_rr", label: "TP1 R:R", prefix: "1:" },
];

function configToForm(c: BotConfig): Record<NumKey, string> {
  return {
    risk_pct: (c.risk_pct * 100).toFixed(2),
    sl_buffer: String(c.sl_buffer),
    min_rr: String(c.min_rr),
    tp1_rr: String(c.tp1_rr),
  };
}

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [config, setConfig] = useState<BotConfig | null>(null);
  const [online, setOnline] = useState<boolean>(true);

  // Editable numeric draft (strings, so partial typing is allowed).
  const [form, setForm] = useState<Record<NumKey, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);

  // MT5 live session (real money). Creds live only in component state; password
  // is cleared the moment a connect attempt returns. No token gate (disabled).
  const [mt5, setMt5] = useState<Mt5Status | null>(null);
  const [mt5Busy, setMt5Busy] = useState(false);
  const [mt5Err, setMt5Err] = useState<string | null>(null);
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [server, setServer] = useState("");

  const poll = useCallback(async () => {
    try {
      const s = await getStatus();
      setStatus(s);
      setOnline(true);
    } catch {
      setOnline(false); // defensive: keep last render, flip the badge
    }
  }, []);

  useEffect(() => {
    poll();
    getConfig().then((c) => { setConfig(c); setForm(configToForm(c)); })
      .catch(() => setOnline(false));
    const id = setInterval(poll, REFRESH);
    return () => clearInterval(id);
  }, [poll]);

  async function toggle(key: keyof BotConfig, value: boolean) {
    if (!config) return;
    setConfig({ ...config, [key]: value }); // optimistic
    try {
      setConfig(await postConfig({ [key]: value }));
    } catch {
      setConfig(config); // revert on failure
      setOnline(false);
    }
  }

  const dirty = !!(config && form &&
    NUM_FIELDS.some(({ key, asPercent }) => {
      const cur = asPercent ? (config[key] * 100).toFixed(2) : String(config[key]);
      return cur !== form[key];
    }));

  async function saveNumbers() {
    if (!form) return;
    setSaveErr(null);
    const patch: Partial<BotConfig> = {};
    for (const { key, asPercent } of NUM_FIELDS) {
      const n = Number(form[key]);
      if (!Number.isFinite(n) || n < 0) { setSaveErr(`${key}: invalid number`); return; }
      patch[key] = asPercent ? n / 100 : n;
    }
    setSaving(true);
    try {
      const c = await postConfig(patch);
      setConfig(c);
      setForm(configToForm(c)); // re-sync from authoritative server values
    } catch (e) {
      setSaveErr(e instanceof Error ? e.message : "save failed");
    } finally {
      setSaving(false);
    }
  }

  async function armLive() {
    setMt5Err(null);
    const loginNum = Number(login);
    if (!Number.isInteger(loginNum) || loginNum <= 0) { setMt5Err("login must be a number"); return; }
    if (!password || !server) { setMt5Err("password and server required"); return; }
    setMt5Busy(true);
    try {
      const res = await connectMt5(loginNum, password, server);
      setMt5(res);
    } catch (e) {
      setMt5Err(e instanceof Error ? e.message : "connect failed");
    } finally {
      setPassword("");      // never keep the password after the attempt
      setMt5Busy(false);
    }
  }

  async function disarmLive() {
    setMt5Err(null);
    setMt5Busy(true);
    try {
      setMt5(await disconnectMt5());
    } catch (e) {
      setMt5Err(e instanceof Error ? e.message : "disconnect failed");
    } finally {
      setMt5Busy(false);
    }
  }

  const armed = !!(mt5?.live_armed);

  const sig = status?.last_signal as Record<string, unknown> | null;
  const isTrade = !!(sig && sig.direction && sig.direction !== "none");

  return (
    <main className="min-h-screen p-4">
      {/* Header */}
      <header className="mb-4 flex items-center gap-4 border-b border-border pb-3">
        <div className="text-[15px] font-bold tracking-wide">
          <span className="text-amber">●</span> XAUUSD QT BOT
        </div>
        <span className={`rounded-sm px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
          status?.mode === "LIVE" ? "bg-up/20 text-up" : "bg-amber/20 text-amber"}`}>
          {status?.mode ?? "—"}
        </span>
        <div className="ml-auto flex items-center gap-2 text-sm">
          {online ? <Wifi className="h-4 w-4 text-up" /> : <WifiOff className="h-4 w-4 text-down" />}
          <span className={online ? "text-up" : "text-down"}>
            {online ? "API connected" : "API offline"}
          </span>
        </div>
      </header>

      {!online && (
        <div className="mb-4 rounded-md border border-down/40 bg-down/10 px-3 py-2 text-sm text-down">
          Backend unreachable — showing last known state. Retrying every {REFRESH / 1000}s…
        </div>
      )}

      <div className="grid gap-3.5 md:grid-cols-2 lg:grid-cols-4">
        {/* Price / engine */}
        <Card>
          <CardTitle><Radio className="mr-1 inline h-3 w-3" />Market</CardTitle>
          {status ? (
            <>
              <div className="mb-2 text-2xl font-bold">{fmt(status.price)}</div>
              <Row k="Engine" v={status.engine} />
              <Row k="Quarter" v={status.quarter ?? "—"} />
              <Row k="In session" v={String(status.in_session ?? "—")} />
              <Row k="Next poll" v={status.next_poll ?? "—"} />
            </>
          ) : <Skeleton className="h-32 w-full" />}
        </Card>

        {/* Bias */}
        <Card>
          <CardTitle><Gauge className="mr-1 inline h-3 w-3" />Bias</CardTitle>
          {status ? (
            <>
              <Row k="Overall" v={status.bias.overall ?? "—"} accent={biasColor(status.bias.overall)} />
              <Row k="Macro" v={status.macro_bias ?? "—"} accent={biasColor(status.macro_bias)} />
              <Row k="Micro" v={status.micro_bias ?? "—"} accent={biasColor(status.micro_bias)} />
              <Row k="Synced" v={status.bias.synchronized === true ? "YES" : status.bias.synchronized === false ? "NO" : "—"} />
              <Row k="POC" v={fmt(status.volume_profile?.poc)} />
            </>
          ) : <Skeleton className="h-32 w-full" />}
        </Card>

        {/* Signal */}
        <Card>
          <CardTitle><Target className="mr-1 inline h-3 w-3" />Latest Signal</CardTitle>
          {status ? (
            <>
              <div className={`mb-2 text-xl font-bold ${
                isTrade ? (sig!.direction === "long" ? "text-up" : "text-down") : "text-down"}`}>
                {isTrade ? String(sig!.direction).toUpperCase() : "NO TRADE"}
              </div>
              {isTrade ? (
                <>
                  <Row k="Entry" v={fmt(sig!.entry)} />
                  <Row k="SL" v={fmt(sig!.sl)} />
                  <Row k="R:R" v={sig!.rr ? `1:${Number(sig!.rr).toFixed(1)}` : "—"} />
                  <Row k="Lots" v={String(sig!.lots ?? "—")} />
                </>
              ) : <div className="text-xs text-muted-foreground">{String(sig?.reason ?? "awaiting setup")}</div>}
            </>
          ) : <Skeleton className="h-32 w-full" />}
        </Card>

        {/* Config panel — editable */}
        <Card>
          <CardTitle><Activity className="mr-1 inline h-3 w-3" />Config</CardTitle>
          {config && form ? (
            <>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-muted-foreground">Strategy</span>
                <Switch checked={config.strategy_enabled}
                  onCheckedChange={(v) => toggle("strategy_enabled", v)} />
              </div>
              <div className="flex items-center justify-between border-b border-border py-1.5">
                <span className="text-muted-foreground">Daily report</span>
                <Switch checked={config.daily_report_enabled}
                  onCheckedChange={(v) => toggle("daily_report_enabled", v)} />
              </div>
              {NUM_FIELDS.map(({ key, label, asPercent, prefix }) => (
                <div key={key} className="flex items-center justify-between gap-2 py-1.5">
                  <span className="text-muted-foreground">{label}</span>
                  <div className="flex w-24 items-center gap-1">
                    {prefix && <span className="text-muted-foreground">{prefix}</span>}
                    <Input
                      type="number" step="any" inputMode="decimal"
                      value={form[key]}
                      onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                    />
                    {asPercent && <span className="text-muted-foreground">%</span>}
                  </div>
                </div>
              ))}
              {saveErr && <div className="mt-1 text-xs text-down">{saveErr}</div>}
              <button
                onClick={saveNumbers}
                disabled={!dirty || saving}
                className="mt-2 w-full rounded-sm bg-amber/20 py-1.5 text-xs font-bold uppercase
                  tracking-wider text-amber transition hover:bg-amber/30 disabled:opacity-40"
              >
                {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
              </button>
            </>
          ) : <Skeleton className="h-32 w-full" />}
        </Card>
      </div>

      {/* MT5 live session — REAL MONEY */}
      <Card className={`mt-3.5 ${armed ? "border-up/50" : "border-down/40"}`}>
        <div className="mb-3 flex items-center gap-2">
          <CardTitle className="mb-0"><Power className="mr-1 inline h-3 w-3" />MT5 Live Session</CardTitle>
          <span className={`rounded-sm px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider ${
            armed ? "bg-up/20 text-up" : "bg-down/20 text-down"}`}>
            {armed ? "● Armed — live orders" : "○ Disarmed"}
          </span>
          {mt5?.account?.balance != null && (
            <span className="ml-auto text-sm text-muted-foreground">
              {mt5.account.login} · {fmt(mt5.account.balance)} {mt5.account.currency ?? ""}
            </span>
          )}
        </div>

        <div className="mb-2 flex items-start gap-2 rounded-md border border-amber/40 bg-amber/10 px-3 py-2 text-xs text-amber">
          <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>Connecting logs in to MetaTrader 5 and <b>arms live order placement</b>. Real funds. Password is sent once and never stored. No token — keep this backend bound to localhost only.</span>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          <Input className="text-left" type="text" inputMode="numeric" placeholder="MT5 login (ID)"
            value={login} onChange={(e) => setLogin(e.target.value)} />
          <Input className="text-left" type="password" placeholder="MT5 password"
            value={password} onChange={(e) => setPassword(e.target.value)} />
          <Input className="text-left" type="text" placeholder="MT5 server"
            value={server} onChange={(e) => setServer(e.target.value)} />
        </div>

        {mt5Err && <div className="mt-2 text-xs text-down">⚠ {mt5Err}</div>}

        <div className="mt-3 flex gap-2">
          <button
            onClick={armLive}
            disabled={mt5Busy || armed}
            className="flex-1 rounded-sm bg-down/20 py-2 text-xs font-bold uppercase tracking-wider
              text-down transition hover:bg-down/30 disabled:opacity-40"
          >
            {mt5Busy ? "Working…" : "Connect — ARM live"}
          </button>
          <button
            onClick={disarmLive}
            disabled={mt5Busy || !armed}
            className="flex-1 rounded-sm border border-border py-2 text-xs font-bold uppercase
              tracking-wider text-muted-foreground transition hover:bg-muted disabled:opacity-40"
          >
            Disconnect — disarm
          </button>
        </div>
      </Card>

      {/* Chart */}
      <Card className="mt-3.5 p-1.5">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/api/chart" alt="XAUUSD chart" className="w-full rounded-sm" />
      </Card>
    </main>
  );
}
