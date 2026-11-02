/** Shape of reports/results.json, written by `mma report`. The dashboard only reads it. */

export type Metric = "project" | "revenue" | "partner_profit" | "contacted";

export interface PolicyStats {
  requests: number;
  matched: number;
  leads: number;
  contacted: number;
  project: number;
  revenue: number;
  partner_profit: number;
  partner_profit_per_lead: number;
}

export interface DesignSummary {
  mean_estimate: number;
  mean_truth: number;
  bias: number;
  relative_bias: number | null;
  coverage: number;
  mean_se: number;
  replications: number;
}

export interface ReliabilityBin {
  predicted: number;
  observed: number;
  n: number;
}

export interface ModelReport {
  rows: { train: number; calib: number; test: number };
  test: { auc: number; ece: number; brier: number; base_rate: number };
  test_uncalibrated: { auc: number; ece: number };
  reliability: ReliabilityBin[];
}

export interface Study {
  profile: string;
  world: { requests_per_month: number; partners: number; regions: number; categories: number };
  prepare: {
    dbt: { nodes: number; tests: number; failed: number };
    parity: { mismatches: number; pairs: number };
    training_rows: number;
    models: { contact: ModelReport; win: ModelReport };
  };
  designs: Record<string, string>;
  experiments: Record<string, Partial<Record<Metric, DesignSummary>>>;
  frontier: Record<string, PolicyStats>;
  aa_budget_split_false_positive_rate?: Partial<Record<Metric, number>>;
}

export interface Interval {
  estimate: number;
  se: number;
  lo: number;
  hi: number;
}

export interface HeldoutWorld {
  name: string;
  about: string;
  rules: PolicyStats;
  model: PolicyStats;
  truth: Partial<Record<Metric, number>>;
  designs: Record<string, Partial<Record<Metric, Interval>>>;
}

export interface Heldout {
  set: string;
  status: string;
  blind: boolean;
  recorded_at?: string;
  summary: {
    scenarios: number;
    project_lift_share: number;
    mean_project_lift: number;
    min_revenue_ratio: number;
    mean_revenue_ratio: number;
    budget_split_project_covered: number;
    request_split_project_covered: number;
  };
  results: HeldoutWorld[];
}

export interface Bench {
  requests: number;
  service_instances: number;
  threads: number;
  cap_squeezed_to: number | null;
  leads: number;
  oversold_leads: number;
  decisions_vs_counter_mismatches: number;
  retry_returns_same_decision: boolean;
  p50_ms: number;
  p95_ms: number;
}

export interface GateCheck {
  name: string;
  op: "==" | "<=" | ">=";
  value: number;
  actual: number | boolean | null;
  ok: boolean;
}

export interface Results {
  generated_at: string;
  profile: string;
  study: Study | null;
  heldout: Heldout | null;
  serving: { contention: Bench; latency: Bench } | null;
  metrics: Record<string, number | boolean | null>;
  gate?: { floors: GateCheck[]; targets: GateCheck[] };
}

export function isResults(x: unknown): x is Results {
  if (typeof x !== "object" || x === null) return false;
  const r = x as Record<string, unknown>;
  return typeof r.generated_at === "string" && typeof r.metrics === "object" && "study" in r;
}
