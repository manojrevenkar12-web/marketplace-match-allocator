import { useState } from "react";
import { share } from "../../shared/lib/format";
import { designLabel, label, metricInfo } from "../../shared/lib/labels";
import type { Metric, Study } from "../../shared/lib/results";
import { Segmented } from "../../shared/ui/Segmented";
import { ExperimentChart } from "./ExperimentChart";
import s from "./experiments.module.css";
import { metricsIn, rowsFor } from "./model";

const words = ["No design", "One design", "Two designs", "Three designs", "Four designs"];
const count = (n: number) => words[n] ?? `${n} designs`;

export function heldText(names: string[], total: number): string {
  if (names.length === total) return "Every design's interval holds it.";
  if (names.length === 0) return "No design's interval holds it.";
  if (names.length === 1) return `Only the ${names[0]}'s interval holds it.`;
  return `Only the intervals of the ${names.slice(0, -1).join(", ")} and ${names.at(-1)} hold it.`;
}

export function Experiments({ study }: { study: Study }) {
  const metrics = metricsIn(study);
  const [metric, setMetric] = useState<Metric>(metrics[0] ?? "project");
  const rows = rowsFor(study, metric);
  const info = metricInfo[metric];
  const truth = rows[0]?.truth ?? 0;
  const held = rows.filter((r) => r.covered);
  const flipped = rows.filter((r) => r.wrongSign);
  const aa = study.aa_budget_split_false_positive_rate?.[metric];
  return (
    <div className={s.hero}>
      <div className={s.controls}>
        <p className={s.verdict} aria-live="polite">
          The model changes {info.unit} by <strong>{info.delta(truth)}</strong>.{" "}
          {heldText(
            held.map((r) => label(designLabel, r.key).toLowerCase()),
            rows.length,
          )}{" "}
          {flipped.length ? `${count(flipped.length)} report${flipped.length === 1 ? "s" : ""} the opposite sign.` : ""}
        </p>
        {metrics.length > 1 ? (
          <Segmented
            label="Outcome"
            options={metrics.map((m) => ({ key: m, label: metricInfo[m].label }))}
            value={metric}
            onChange={setMetric}
          />
        ) : null}
      </div>
      <ExperimentChart rows={rows} metric={metric} />
      {aa !== undefined ? (
        <p className={s.footnote}>
          A/A check on the budget split (current rules in both arms): a significant difference in {share(aa, 0)} of runs, where 5% is
          expected.
        </p>
      ) : null}
    </div>
  );
}
