import { describe, expect, it } from "vitest";
import type { Results } from "../../shared/lib/results";
import fixture from "../../test/fixture.json";
import { metricsIn, rowsFor } from "./model";

const study = (fixture as unknown as Results).study!;

describe("experiment rows", () => {
  it("draws one row per design with a 95% interval around the mean estimate", () => {
    const rows = rowsFor(study, "project");
    expect(rows.map((r) => r.key)).toEqual(Object.keys(study.experiments));
    for (const r of rows) {
      expect(r.lo).toBeLessThan(r.estimate);
      expect(r.hi).toBeGreaterThan(r.estimate);
    }
  });
  it("marks whether an interval holds the true effect and whether the sign flipped", () => {
    const rows = Object.fromEntries(rowsFor(study, "project").map((r) => [r.key, r]));
    expect(rows.budget_split.covered).toBe(true);
    expect(rows.request_split.covered).toBe(false);
    expect(rows.request_split.wrongSign).toBe(true);
  });
  it("lists the outcomes that were measured", () => {
    expect(metricsIn(study)).toContain("project");
  });
});
