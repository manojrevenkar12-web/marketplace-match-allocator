import type { DesignSummary, Metric, Study } from "../../shared/lib/results";
import { z95 } from "../../shared/theme/tokens";

export interface DesignRow {
  key: string;
  description: string;
  estimate: number;
  lo: number;
  hi: number;
  truth: number;
  covered: boolean;
  wrongSign: boolean;
  coverage: number;
  replications: number;
}

export function rowsFor(study: Study, metric: Metric): DesignRow[] {
  return Object.entries(study.experiments).flatMap(([key, byMetric]) => {
    const d: DesignSummary | undefined = byMetric[metric];
    if (!d) return [];
    const half = z95 * d.mean_se;
    const lo = d.mean_estimate - half;
    const hi = d.mean_estimate + half;
    return [
      {
        key,
        description: study.designs[key] ?? "",
        estimate: d.mean_estimate,
        lo,
        hi,
        truth: d.mean_truth,
        covered: lo <= d.mean_truth && d.mean_truth <= hi,
        wrongSign: Math.sign(d.mean_estimate) !== Math.sign(d.mean_truth) && d.mean_truth !== 0,
        coverage: d.coverage,
        replications: d.replications,
      },
    ];
  });
}

export function metricsIn(study: Study): Metric[] {
  const order: Metric[] = ["project", "revenue", "partner_profit", "contacted"];
  return order.filter((m) => Object.values(study.experiments).some((d) => d[m]));
}
