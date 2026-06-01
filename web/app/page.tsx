"use client";

import { useEffect, useState, useCallback } from "react";
import { Activity, Gauge, Radio, Target, Wifi, WifiOff } from "lucide-react";
import { Card, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Skeleton } from "@/components/ui/skeleton";
import { getStatus, getConfig, postConfig, type Status, type BotConfig } from "@/lib/api";

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

export default function Dashboard() {
  const [status, setStatus] = useState<Status | null>(null);
  const [config, setConfig] = useState<BotConfig | null>(null);
  const [online, setOnline] = useState<boolean>(true);

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
    getConfig().then(setConfig).catch(() => setOnline(false));
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

        {/* Config panel */}
        <Card>
          <CardTitle><Activity className="mr-1 inline h-3 w-3" />Config</CardTitle>
          {config ? (
            <>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-muted-foreground">Strategy</span>
                <Switch checked={config.strategy_enabled}
                  onCheckedChange={(v) => toggle("strategy_enabled", v)} />
              </div>
              <div className="flex items-center justify-between py-1.5">
                <span className="text-muted-foreground">Daily report</span>
                <Switch checked={config.daily_report_enabled}
                  onCheckedChange={(v) => toggle("daily_report_enabled", v)} />
              </div>
              <Row k="Risk %" v={(config.risk_pct * 100).toFixed(2) + "%"} />
              <Row k="SL buffer" v={config.sl_buffer} />
              <Row k="Min R:R" v={`1:${config.min_rr}`} />
            </>
          ) : <Skeleton className="h-32 w-full" />}
        </Card>
      </div>

      {/* Chart */}
      <Card className="mt-3.5 p-1.5">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/api/chart" alt="XAUUSD chart" className="w-full rounded-sm" />
      </Card>
    </main>
  );
}
