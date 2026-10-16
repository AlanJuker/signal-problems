import { describe, expect, it } from "vitest";

import { parsePeriod, sinceFor } from "./period";

describe("period", () => {
  it("counts back from the last day in the data, both ends included", () => {
    expect(sinceFor("12m", "2026-08-31")).toBe("2025-09-01");
    expect(sinceFor("3y", "2026-08-31")).toBe("2023-09-02");
  });

  it("has no start for the whole history or before the data has loaded", () => {
    expect(sinceFor("all", "2026-08-31")).toBeUndefined();
    expect(sinceFor("12m", undefined)).toBeUndefined();
  });

  it("falls back to the past 12 months for unknown values", () => {
    expect(parsePeriod("3y")).toBe("3y");
    expect(parsePeriod("forever")).toBe("12m");
    expect(parsePeriod(null)).toBe("12m");
  });
});
