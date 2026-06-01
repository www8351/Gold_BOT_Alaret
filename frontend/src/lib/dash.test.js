import { describe, it, expect } from "vitest";
import { fmt, scaleTicks, gaugeParams, isTrade } from "./dash.js";

describe("fmt", () => {
  it("formats numbers to 2dp", () => expect(fmt(2000.5)).toBe("2000.50"));
  it("dash for null", () => expect(fmt(null)).toBe("—"));
  it("passes strings", () => expect(fmt("Q3")).toBe("Q3"));
});

describe("scaleTicks", () => {
  it("returns [] with fewer than 2 numbers", () => {
    expect(scaleTicks(null, {})).toEqual([]);
    expect(scaleTicks(2000, {})).toEqual([]);
  });
  it("highest value gets smallest topPct", () => {
    const t = scaleTicks(2000, { TDO: 1990, TWO: 2010 });
    expect(t[0].name).toBe("TWO");        // 2010 highest -> first
    expect(t[0].topPct).toBeLessThan(t[t.length - 1].topPct);
  });
  it("price marker flagged", () => {
    const t = scaleTicks(2000, { TDO: 1990 });
    expect(t.find((x) => x.kind === "price").name).toBe("Price");
  });
});

describe("gaugeParams", () => {
  it("bearish synced = full red", () => {
    const g = gaugeParams({ overall: "bearish", synchronized: true });
    expect(g.color).toBe("#f23645");
    expect(g.label).toBe("BEAR");
    expect(g.offset).toBeCloseTo(0, 5);   // pct 1.0 -> offset 0
  });
  it("neutral = half gray", () => {
    const g = gaugeParams({ overall: "neutral" });
    expect(g.label).toBe("FLAT");
    expect(g.offset).toBeCloseTo(g.circumference / 2, 5);
  });
});

describe("isTrade", () => {
  it("true for long", () => expect(isTrade({ direction: "long" })).toBe(true));
  it("false for none/empty", () => {
    expect(isTrade({ direction: "none" })).toBe(false);
    expect(isTrade(null)).toBe(false);
  });
});
