import { describe, expect, it } from "vitest";
import { eurDelta, lift, pp, share } from "./format";
import { linear, niceStep } from "./scale";

describe("scale", () => {
  it("always includes zero and maps the domain onto 0..100", () => {
    const s = linear([0.02, 0.05]);
    expect(s.ticks).toContain(0);
    expect(s.at(s.domain[0])).toBe(0);
    expect(s.at(s.domain[1])).toBe(100);
  });
  it("picks round steps", () => {
    expect(niceStep(0.07, 5)).toBeCloseTo(0.02);
    expect(niceStep(130, 5)).toBe(50);
  });
  it("survives a constant series", () => {
    expect(linear([0, 0]).domain[1]).toBeGreaterThan(0);
  });
});

describe("format", () => {
  it("signs with a true minus", () => {
    expect(lift(-0.064)).toBe("−6.4%");
    expect(lift(0.112)).toBe("+11.2%");
    expect(pp(0.0114)).toBe("+1.14 pp");
    expect(eurDelta(-3.25)).toBe("−€3.3");
    expect(share(0.1059, 2)).toBe("10.59%");
  });
});
