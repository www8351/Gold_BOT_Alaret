"""aiohttp monitoring dashboard, embedded in the bot's asyncio loop.

All routes are guarded by a token (query `?token=` or header `X-Token`),
compared constant-time. The page polls /api/state every few seconds and
renders four sections: Status, Levels+Bias, Last Signal, Chart+Log.
"""
from __future__ import annotations

import hmac
import logging
import os

from aiohttp import web

logger = logging.getLogger(__name__)

REFRESH_SECONDS = int(os.getenv("DASHBOARD_REFRESH_SEC", "5"))


def _check_token(request: web.Request, token: str) -> bool:
    provided = request.query.get("token") or request.headers.get("X-Token") or ""
    return hmac.compare_digest(str(provided), token)


# The index page is a public shell (no data); the user enters the token there
# to authenticate the data calls. /health is public for uptime probes.
# Everything else stays gated.
_PUBLIC_PATHS = {"/", "/health"}


@web.middleware
async def _token_middleware(request: web.Request, handler):
    if request.path not in _PUBLIC_PATHS:
        token = request.app["token"]
        if not _check_token(request, token):
            return web.json_response({"error": "unauthorized"}, status=401)
    return await handler(request)


async def _handle_state(request: web.Request) -> web.Response:
    return web.json_response(request.app["state"].snapshot())


async def _handle_chart(request: web.Request) -> web.Response:
    path = request.app["chart_path"]
    if not os.path.exists(path):
        return web.json_response({"error": "no chart yet"}, status=404)
    return web.FileResponse(path)


async def _handle_index(request: web.Request) -> web.Response:
    return web.Response(text=_PAGE_HTML, content_type="text/html")


async def _handle_health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_app(state, token: str, chart_path: str = "gold_chart.png") -> web.Application:
    app = web.Application(middlewares=[_token_middleware])
    app["state"] = state
    app["token"] = token
    app["chart_path"] = chart_path
    app.router.add_get("/", _handle_index)
    app.router.add_get("/health", _handle_health)
    app.router.add_get("/api/state", _handle_state)
    app.router.add_get("/chart.png", _handle_chart)
    return app


async def start_dashboard(state, host: str, port: int, token: str,
                          chart_path: str = "gold_chart.png"):
    """Start the dashboard on the current loop. Returns (runner, site)."""
    app = create_app(state, token=token, chart_path=chart_path)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logger.info("📊 Dashboard live on http://%s:%d  (token required)", host, port)
    return runner, site


_PAGE_HTML = """<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>XAUUSD Bot Dashboard</title>
<style>
  :root {
    color-scheme: dark;
    --bg:#131722; --panel:#1e222d; --panel2:#181c27; --border:#2a2e39;
    --text:#d1d4dc; --muted:#787b86; --accent:#22d3ee;
    --green:#089981; --red:#f23645; --amber:#f7931a;
  }
  * { box-sizing:border-box; }
  body { background:var(--bg); color:var(--text); margin:0; padding:0;
         font:13px/1.45 "Trebuchet MS","Helvetica Neue",system-ui,sans-serif;
         font-variant-numeric:tabular-nums; }

  /* === HEADER === */
  header { display:flex; align-items:center; gap:18px; padding:10px 18px;
           background:var(--panel); border-bottom:1px solid var(--border); }
  .brand { font-size:15px; font-weight:700; letter-spacing:.04em; color:var(--text); }
  .brand .sym { color:var(--amber); margin-right:6px; }
  .pill { padding:3px 9px; border-radius:4px; font-weight:700; font-size:11px;
          letter-spacing:.06em; text-transform:uppercase; }
  .live { background:rgba(8,153,129,.18); color:var(--green); }
  .dry  { background:rgba(247,147,26,.18); color:var(--amber); }
  .price-big { margin-left:auto; display:flex; align-items:baseline; gap:8px; }
  .price-big .lbl { color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.08em; }
  .price-big .val { font-size:22px; font-weight:700; color:var(--text); }
  .tok-wrap { display:flex; gap:6px; }
  .tok-wrap input { background:var(--bg); color:var(--text); border:1px solid var(--border);
                    border-radius:3px; padding:5px 8px; font:inherit; min-width:160px; }
  .tok-wrap button { background:var(--green); color:#fff; border:0; border-radius:3px;
                     padding:5px 12px; cursor:pointer; font:inherit; font-weight:600; }
  .tok-wrap button:hover { filter:brightness(1.1); }
  #err { color:var(--red); padding:0 18px; min-height:18px; font-size:12px; }

  /* === LAYOUT === */
  .wrap { padding:14px; display:grid; gap:14px;
          grid-template-columns: 280px 280px 1fr;
          grid-template-areas:
            "status levels  signal"
            "chart  chart   chart"
            "log    log     log"; }
  @media (max-width:980px) {
    .wrap { grid-template-columns: 1fr;
            grid-template-areas: "status" "levels" "signal" "chart" "log"; }
  }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:4px;
          padding:12px 14px; }
  .card h2 { font-size:11px; text-transform:uppercase; letter-spacing:.1em;
             color:var(--muted); margin:0 0 10px; font-weight:600; }

  .row { display:flex; justify-content:space-between; padding:5px 0;
         border-bottom:1px solid var(--border); }
  .row:last-child { border-bottom:0; }
  .k { color:var(--muted); } .v { color:var(--text); }
  .v.long  { color:var(--green); font-weight:700; }
  .v.short { color:var(--red);   font-weight:700; }
  .v.none  { color:var(--muted); }

  /* === LEVELS vertical scale === */
  #status { grid-area:status; }
  #levels-card { grid-area:levels; }
  .scale { position:relative; height:240px; margin:6px 4px 4px 4px;
           border-left:1px solid var(--border); }
  .scale .tick { position:absolute; left:-1px; display:flex; align-items:center;
                 gap:6px; font-size:11px; transform:translateY(-50%); white-space:nowrap; }
  .scale .tick .dot { width:6px; height:6px; border-radius:50%; background:var(--accent);
                      box-shadow:0 0 4px var(--accent); }
  .scale .tick .lbl { color:var(--muted); }
  .scale .tick .px  { color:var(--text); margin-left:4px; }
  .scale .tick.price .dot { background:var(--amber); box-shadow:0 0 6px var(--amber); }
  .scale .tick.price .lbl { color:var(--amber); font-weight:700; }

  /* === BIAS GAUGE + SIGNAL === */
  #signal-card { grid-area:signal; display:flex; flex-direction:column; gap:12px; }
  .gauge-wrap { display:flex; align-items:center; gap:14px; }
  .gauge { width:120px; height:120px; flex-shrink:0; }
  .gauge .bg-ring { fill:none; stroke:var(--border); stroke-width:10; }
  .gauge .fg-ring { fill:none; stroke-width:10; stroke-linecap:round;
                    transform:rotate(-90deg); transform-origin:center;
                    transition:stroke-dashoffset .4s, stroke .4s; }
  .gauge text { text-anchor:middle; dominant-baseline:central;
                font-family:inherit; font-weight:700; }
  .gauge .label { font-size:9px; fill:var(--muted); letter-spacing:.1em; }
  .gauge .value { font-size:14px; }
  .bias-meta { flex:1; }
  .bias-meta .row { padding:4px 0; }

  .banner { padding:18px; border-radius:4px; text-align:center;
            font-size:20px; font-weight:700; letter-spacing:.08em;
            border:1px solid var(--border); }
  .banner.no-trade { background:rgba(242,54,69,.12); color:var(--red);
                     border-color:rgba(242,54,69,.4); }
  .banner.long     { background:rgba(8,153,129,.14); color:var(--green);
                     border-color:rgba(8,153,129,.4); }
  .banner.short    { background:rgba(242,54,69,.14); color:var(--red);
                     border-color:rgba(242,54,69,.4); }
  .banner .sub { display:block; font-size:11px; font-weight:500; margin-top:4px;
                 letter-spacing:.06em; color:var(--muted); }
  .sig-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-top:8px; }
  .sig-cell { background:var(--panel2); border:1px solid var(--border); border-radius:3px;
              padding:6px 8px; }
  .sig-cell .k { font-size:10px; text-transform:uppercase; letter-spacing:.08em; }
  .sig-cell .v { font-size:13px; font-weight:600; display:block; margin-top:2px; }

  /* === CHART + LOG === */
  #chart-card { grid-area:chart; padding:6px; }
  #chart { width:100%; display:block; border-radius:3px; }
  #log-card { grid-area:log; }
  pre { background:var(--panel2); border:1px solid var(--border); border-radius:3px;
        padding:8px 10px; overflow:auto; max-height:200px; font-size:11px;
        margin:0; font-family:"Consolas","Monaco",monospace; color:var(--text); }
</style></head>
<body>

<header>
  <div class="brand"><span class="sym">●</span>XAUUSD QT BOT</div>
  <span id="mode" class="pill dry">DRY-RUN</span>
  <div class="price-big">
    <span class="lbl">Price</span><span id="price-big" class="val">—</span>
  </div>
  <div class="tok-wrap">
    <input id="tok" type="password" placeholder="dashboard token">
    <button id="save">Connect</button>
  </div>
</header>
<div id="err"></div>

<div class="wrap">

  <div class="card" id="status">
    <h2>Status</h2><div id="status-body"></div>
  </div>

  <div class="card" id="levels-card">
    <h2>Key Levels &amp; Bias</h2>
    <div class="scale" id="scale"></div>
  </div>

  <div class="card" id="signal-card">
    <h2>Bias &amp; Signal</h2>
    <div class="gauge-wrap">
      <svg class="gauge" viewBox="0 0 120 120">
        <circle class="bg-ring" cx="60" cy="60" r="50"/>
        <circle id="gauge-fg" class="fg-ring" cx="60" cy="60" r="50"
                stroke="#787b86" stroke-dasharray="314" stroke-dashoffset="314"/>
        <text class="label" x="60" y="50">BIAS</text>
        <text id="gauge-val" class="value" x="60" y="68" fill="#d1d4dc">—</text>
      </svg>
      <div class="bias-meta" id="bias-meta"></div>
    </div>
    <div id="banner" class="banner no-trade">NO TRADE
      <span class="sub" id="banner-sub">awaiting setup</span>
    </div>
    <div class="sig-grid" id="sig-grid" style="display:none"></div>
  </div>

  <div class="card" id="chart-card"><img id="chart" alt="chart"></div>
  <div class="card" id="log-card"><h2>Event Log</h2><pre id="log"></pre></div>

</div>

<script>
let TOKEN = new URLSearchParams(location.search).get('token')
           || localStorage.getItem('qt_token') || '';
const REFRESH = %REFRESH% * 1000;
const $ = id => document.getElementById(id);
function saveToken(){ TOKEN = $('tok').value.trim(); localStorage.setItem('qt_token', TOKEN); tick(); }

function rows(obj){
  return Object.entries(obj).map(([k,v]) =>
    `<div class="row"><span class="k">${k}</span><span class="v">${v ?? '—'}</span></div>`
  ).join('');
}
function fmt(v){ return (typeof v === 'number') ? v.toFixed(2) : (v ?? '—'); }

function drawScale(price, levels){
  const el = $('scale');
  el.innerHTML = '';
  const items = [];
  if (typeof price === 'number') items.push(['Price', price, 'price']);
  for (const [k,v] of Object.entries(levels||{})) {
    if (typeof v === 'number') items.push([k, v, '']);
  }
  if (items.length < 2) {
    el.innerHTML = '<div style="color:var(--muted);padding:8px;font-size:11px">awaiting data…</div>';
    return;
  }
  const vals = items.map(i=>i[1]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.08;
  lo -= pad; hi += pad;
  items.sort((a,b)=>b[1]-a[1]);  // top = highest
  for (const [name, v, cls] of items) {
    const pct = (hi - v) / (hi - lo) * 100;
    el.insertAdjacentHTML('beforeend',
      `<div class="tick ${cls}" style="top:${pct.toFixed(2)}%">
         <span class="dot"></span><span class="lbl">${name}</span><span class="px">${v.toFixed(2)}</span>
       </div>`);
  }
}

function drawGauge(bias){
  const ov = (bias && bias.overall) || 'neutral';
  const sync = bias && bias.synchronized;
  // map: bullish=full green right, bearish=full red left, neutral=half gray
  const C = 2 * Math.PI * 50;  // ~314
  let pct, color, label;
  if (ov === 'bullish') { pct = sync ? 1.0 : 0.66; color = '#089981'; label = 'BULL'; }
  else if (ov === 'bearish') { pct = sync ? 1.0 : 0.66; color = '#f23645'; label = 'BEAR'; }
  else { pct = 0.5; color = '#787b86'; label = 'FLAT'; }
  $('gauge-fg').setAttribute('stroke', color);
  $('gauge-fg').setAttribute('stroke-dashoffset', (C * (1 - pct)).toFixed(1));
  $('gauge-val').textContent = label;
  $('gauge-val').setAttribute('fill', color);
}

function drawSignal(sig){
  const banner = $('banner'), sub = $('banner-sub'), grid = $('sig-grid');
  if (sig && sig.direction && sig.direction !== 'none') {
    const dir = sig.direction;
    banner.className = 'banner ' + dir;
    banner.firstChild.nodeValue = dir.toUpperCase();
    sub.textContent = `entry ${fmt(sig.entry)}  •  R:R 1:${sig.rr ? Number(sig.rr).toFixed(1) : '—'}`;
    grid.style.display = 'grid';
    grid.innerHTML = [
      ['Entry', fmt(sig.entry)],
      ['SL',    fmt(sig.sl)],
      ['TP1',   fmt(sig.tp1)],
      ['TP2',   fmt(sig.tp2)],
      ['Lots',  sig.lots ?? '—'],
      ['R:R',   sig.rr ? '1:'+Number(sig.rr).toFixed(1) : '—'],
      ['Conf.', (sig.confidence ?? '—')+'/10'],
      ['Dir',   dir.toUpperCase()],
    ].map(([k,v])=>`<div class="sig-cell"><span class="k">${k}</span><span class="v">${v}</span></div>`).join('');
  } else {
    banner.className = 'banner no-trade';
    banner.firstChild.nodeValue = 'NO TRADE';
    sub.textContent = (sig && sig.reason) ? sig.reason : 'awaiting setup';
    grid.style.display = 'none';
    grid.innerHTML = '';
  }
}

async function tick(){
  try {
    const r = await fetch('/api/state?token=' + encodeURIComponent(TOKEN));
    if (!r.ok) { $('err').textContent = 'auth/error: HTTP ' + r.status; return; }
    $('err').textContent = '';
    const s = await r.json();

    const m = $('mode');
    m.textContent = s.mode;
    m.className = 'pill ' + (s.mode === 'LIVE' ? 'live' : 'dry');

    $('price-big').textContent = fmt(s.price);

    $('status-body').innerHTML = rows({
      Quarter:    s.quarter,
      'In session': s.in_session,
      'Next poll': s.next_poll,
      Started:    s.started_at,
    });

    drawScale(s.price, s.levels || {});

    const b = s.bias || {};
    $('bias-meta').innerHTML = rows({
      Overall: b.overall || '—',
      Synced:  (b.synchronized === true ? 'YES' : b.synchronized === false ? 'NO' : '—'),
      POC:     fmt((s.volume_profile || {}).poc),
    });
    drawGauge(b);

    drawSignal(s.last_signal);

    $('chart').src = '/chart.png?token=' + encodeURIComponent(TOKEN) + '&t=' + Date.now();
    $('log').textContent = (s.events || []).map(e => `${e.ts || ''}  ${e.msg}`).join('\\n');
  } catch(e) {
    $('err').textContent = 'fetch failed: ' + e;
  }
}

$('tok').value = TOKEN;
$('save').addEventListener('click', saveToken);
$('tok').addEventListener('keydown', e => { if (e.key === 'Enter') saveToken(); });
tick(); setInterval(tick, REFRESH);
</script></body></html>""".replace("%REFRESH%", str(REFRESH_SECONDS))
