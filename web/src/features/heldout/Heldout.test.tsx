import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Heldout as H, PolicyStats } from "../../shared/lib/results";
import { Heldout } from "./Heldout";

const p = (project: number, revenue: number): PolicyStats => ({
  requests: 100,
  matched: 0.8,
  leads: 200,
  contacted: 0.7,
  project,
  revenue,
  partner_profit: 10,
  partner_profit_per_lead: 50,
});

const h: H = {
  set: "v1",
  status: "heldout",
  blind: true,
  summary: {
    scenarios: 2,
    project_lift_share: 0.5,
    mean_project_lift: 0.001,
    min_revenue_ratio: 0.95,
    mean_revenue_ratio: 1,
    budget_split_project_covered: 0.5,
    request_split_project_covered: 0,
  },
  results: [
    {
      name: "01-partner-shortage",
      about: "Few partners",
      rules: p(0.1, 100),
      model: p(0.11, 101),
      truth: { project: 0.01 },
      designs: { budget_split: { project: { estimate: 0.01, se: 0.004, lo: 0.002, hi: 0.018 } } },
    },
    {
      name: "02-partner-glut",
      about: "Many partners",
      rules: p(0.12, 100),
      model: p(0.118, 95),
      truth: { project: -0.002 },
      designs: { budget_split: { project: { estimate: 0.02, se: 0.004, lo: 0.012, hi: 0.028 } } },
    },
  ],
};

describe("Heldout", () => {
  it("says the first run is kept and marks which worlds the budget split got right", () => {
    render(<Heldout h={h} />);
    expect(screen.getByText(/first run, kept as recorded/)).toBeTruthy();
    expect(screen.getByTestId("world-01-partner-shortage").textContent).toMatch(/Yes/);
    expect(screen.getByTestId("world-02-partner-glut").textContent).toMatch(/No/);
    expect(screen.getByText("partner shortage")).toBeTruthy();
    expect(screen.getByText(/in 1 of 2 markets, with revenue at least 95.0%/)).toBeTruthy();
  });
});
