import { describe, expect, it } from "vitest";

import { LINES } from "../../test/server";
import { DX, DY, computeLayout } from "./layout";

const layout = computeLayout({
  "1": LINES[0].stations.map((s) => s.id),
  "2": LINES[1].stations.map((s) => s.id),
  "4": LINES[2].stations.map((s) => s.id),
});
const at = (id: string) => layout.nodes.get(id)!;

describe("computeLayout", () => {
  it("places every station once", () => {
    expect(layout.nodes.size).toBe(12);
  });

  it("runs Line 2 west to east on one row", () => {
    const xs = LINES[1].stations.map((s) => at(s.id).x);
    expect(xs).toEqual([...xs].sort((a, b) => a - b));
    expect(new Set(LINES[1].stations.map((s) => at(s.id).y)).size).toBe(1);
  });

  it("draws Line 1 as a U with Union at the bottom, between the two arms", () => {
    const union = at("union");
    expect(union.y).toBeGreaterThan(at("museum").y);
    expect(union.y).toBeGreaterThan(at("king").y);
    expect(union.x).toBe((at("st-george").x + at("bloor-yonge").x) / 2);
  });

  it("stacks the northern branches above Line 2", () => {
    expect(at("dupont")).toMatchObject({ x: at("spadina").x, y: at("spadina").y - DY });
    expect(at("sheppard-yonge").x).toBe(at("bloor-yonge").x);
    expect(at("sheppard-yonge").y).toBeLessThan(at("bloor-yonge").y);
  });

  it("branches Line 4 east from Sheppard-Yonge", () => {
    expect(at("don-mills").y).toBe(at("sheppard-yonge").y);
    expect(at("don-mills").x).toBeCloseTo(at("sheppard-yonge").x + DX * 1.4);
  });

  it("follows each line's station order in its route", () => {
    expect(layout.routes["4"]).toEqual([at("sheppard-yonge"), at("don-mills")]);
    expect(layout.routes["1"]).toHaveLength(8);
  });

  it("sizes the canvas to fit every station", () => {
    for (const node of layout.nodes.values()) {
      expect(node.x).toBeLessThan(layout.width);
      expect(node.y).toBeLessThan(layout.height);
    }
  });
});
