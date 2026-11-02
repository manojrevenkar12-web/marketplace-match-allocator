import { eurDelta, pp } from "./format";
import type { Metric } from "./results";

export const designLabel: Record<string, string> = {
  request_split: "Request split",
  budget_split: "Budget split",
  region_split: "Region split",
  switchback: "Switchback",
};

export const policyLabel: Record<string, string> = {
  rules: "Current rules",
  balanced: "Model, balanced",
  revenue_first: "Model, revenue first",
  homeowner_first: "Model, homeowner first",
  partner_first: "Model, partner first",
  balanced_without_pacing: "Model, without pacing",
};

export const metricInfo: Record<Metric, { label: string; unit: string; tickScale: number; delta: (v: number, digits?: number) => string }> =
  {
    project: { label: "Projects", unit: "projects won per request", tickScale: 100, delta: (v, d) => pp(v, d) },
    revenue: { label: "Revenue", unit: "lead revenue per request", tickScale: 1, delta: (v, d) => eurDelta(v, d) },
    partner_profit: { label: "Partner profit", unit: "partner profit per request", tickScale: 1, delta: (v, d) => eurDelta(v, d) },
    contacted: { label: "Contacted", unit: "requests where a partner called", tickScale: 100, delta: (v, d) => pp(v, d) },
  };

export const label = (map: Record<string, string>, key: string) => map[key] ?? key.replaceAll("_", " ");
