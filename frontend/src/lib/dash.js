// Pure presentation helpers for the dashboard (unit-tested, no React/DOM).

export function fmt(v) {
  return typeof v === "number" ? v.toFixed(2) : v ?? "—";
}

// Build the vertical price-scale ticks: each level/price mapped to a top%
// (0% = top = highest price). Returns [] when there are fewer than 2 numbers.
export function scaleTicks(price, levels) {
  const items = [];
  if (typeof price === "number") items.push({ name: "Price", value: price, kind: "price" });
  for (const [k, v] of Object.entries(levels || {})) {
    if (typeof v === "number") items.push({ name: k, value: v, kind: "level" });
  }
  if (items.length < 2) return [];

  const vals = items.map((i) => i.value);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { hi += 1; lo -= 1; }
  const pad = (hi - lo) * 0.08;
  lo -= pad; hi += pad;

  items.sort((a, b) => b.value - a.value); // top = highest
  return items.map((it) => ({ ...it, topPct: ((hi - it.value) / (hi - lo)) * 100 }));
}

// Circular bias gauge parameters. r=50 ring.
export function gaugeParams(bias) {
  const overall = (bias && bias.overall) || "neutral";
  const sync = bias && bias.synchronized;
  const C = 2 * Math.PI * 50;
  let pct, color, label;
  if (overall === "bullish") { pct = sync ? 1.0 : 0.66; color = "#089981"; label = "BULL"; }
  else if (overall === "bearish") { pct = sync ? 1.0 : 0.66; color = "#f23645"; label = "BEAR"; }
  else { pct = 0.5; color = "#787b86"; label = "FLAT"; }
  return { circumference: C, offset: C * (1 - pct), color, label };
}

export function isTrade(sig) {
  return !!(sig && sig.direction && sig.direction !== "none");
}
