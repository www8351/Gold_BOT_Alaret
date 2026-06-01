import { useState } from "react";
import { fmt, scaleTicks, gaugeParams, isTrade } from "../lib/dash.js";

function Rows({ data }) {
  return (
    <>
      {Object.entries(data).map(([k, v]) => (
        <div className="row" key={k}>
          <span className="k">{k}</span>
          <span className="v">{v ?? "—"}</span>
        </div>
      ))}
    </>
  );
}

export function Header({ state, token, onConnect }) {
  const [val, setVal] = useState(token);
  const mode = state?.mode || "DRY-RUN";
  return (
    <header>
      <div className="brand"><span className="sym">●</span>XAUUSD QT BOT</div>
      <span className={"pill " + (mode === "LIVE" ? "live" : "dry")}>{mode}</span>
      <div className="price-big">
        <span className="lbl">Price</span>
        <span className="val">{fmt(state?.price)}</span>
      </div>
      <div className="tok-wrap">
        <input
          type="password" placeholder="dashboard token" value={val}
          onChange={(e) => setVal(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter") onConnect(val.trim()); }}
        />
        <button onClick={() => onConnect(val.trim())}>Connect</button>
      </div>
    </header>
  );
}

export function StatusCard({ state }) {
  return (
    <div className="card status">
      <h2>Status</h2>
      <Rows data={{
        Quarter: state?.quarter,
        "In session": state?.in_session,
        "Next poll": state?.next_poll,
        Started: state?.started_at,
      }} />
    </div>
  );
}

export function LevelsCard({ state }) {
  const ticks = scaleTicks(state?.price, state?.levels || {});
  return (
    <div className="card levels-card">
      <h2>Key Levels &amp; Bias</h2>
      <div className="scale">
        {ticks.length < 2 ? (
          <div style={{ color: "var(--muted)", padding: "8px", fontSize: "11px" }}>awaiting data…</div>
        ) : (
          ticks.map((t) => (
            <div className={"tick " + (t.kind === "price" ? "price" : "")}
                 style={{ top: `${t.topPct.toFixed(2)}%` }} key={t.name}>
              <span className="dot" /><span className="lbl">{t.name}</span>
              <span className="px">{t.value.toFixed(2)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

export function SignalCard({ state }) {
  const bias = state?.bias || {};
  const g = gaugeParams(bias);
  const sig = state?.last_signal;
  const trade = isTrade(sig);
  const dir = trade ? sig.direction : "no-trade";
  const cells = trade ? [
    ["Entry", fmt(sig.entry)], ["SL", fmt(sig.sl)], ["TP1", fmt(sig.tp1)], ["TP2", fmt(sig.tp2)],
    ["Lots", sig.lots ?? "—"], ["R:R", sig.rr ? "1:" + Number(sig.rr).toFixed(1) : "—"],
    ["Conf.", (sig.confidence ?? "—") + "/10"], ["Dir", sig.direction.toUpperCase()],
  ] : [];
  return (
    <div className="card signal-card">
      <h2>Bias &amp; Signal</h2>
      <div className="gauge-wrap">
        <svg className="gauge" viewBox="0 0 120 120">
          <circle className="bg-ring" cx="60" cy="60" r="50" />
          <circle className="fg-ring" cx="60" cy="60" r="50"
                  stroke={g.color} strokeDasharray={g.circumference}
                  strokeDashoffset={g.offset} />
          <text className="label" x="60" y="50">BIAS</text>
          <text className="value" x="60" y="68" fill={g.color}>{g.label}</text>
        </svg>
        <div className="bias-meta">
          <Rows data={{
            Overall: bias.overall || "—",
            Synced: bias.synchronized === true ? "YES" : bias.synchronized === false ? "NO" : "—",
            POC: fmt((state?.volume_profile || {}).poc),
          }} />
        </div>
      </div>
      <div className={"banner " + dir}>
        {trade ? sig.direction.toUpperCase() : "NO TRADE"}
        <span className="sub">
          {trade
            ? `entry ${fmt(sig.entry)}  •  R:R 1:${sig.rr ? Number(sig.rr).toFixed(1) : "—"}`
            : (sig?.reason || "awaiting setup")}
        </span>
      </div>
      {trade && (
        <div className="sig-grid">
          {cells.map(([k, v]) => (
            <div className="sig-cell" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ChartCard({ token, nonce }) {
  return (
    <div className="card chart-card">
      <img src={`/chart.png?token=${encodeURIComponent(token)}&t=${nonce}`} alt="XAUUSD chart" />
    </div>
  );
}

export function LogCard({ state }) {
  const text = (state?.events || []).map((e) => `${e.ts || ""}  ${e.msg}`).join("\n");
  return (
    <div className="card log-card">
      <h2>Event Log</h2>
      <pre>{text}</pre>
    </div>
  );
}
