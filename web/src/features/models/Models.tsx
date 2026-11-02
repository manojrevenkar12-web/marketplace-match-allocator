import { fixed, int, share } from "../../shared/lib/format";
import type { ModelReport, Study } from "../../shared/lib/results";
import s from "./models.module.css";
import { Reliability } from "./Reliability";

const about: Record<string, { title: string; text: string }> = {
  contact: { title: "Will the partner call?", text: "Label: the partner called the homeowner within three days of the lead." },
  win: { title: "Will the partner win the project?", text: "Label: the homeowner signed with the partner within forty days." },
};

function ModelCard({ name, m }: { name: string; m: ModelReport }) {
  const a = about[name] ?? { title: name, text: "" };
  return (
    <article className={s.card} data-testid={`model-${name}`}>
      <h3>{a.title}</h3>
      <p>
        {a.text} Gradient-boosted trees, then isotonic calibration on a later slice; scored on the latest slice ({int(m.rows.test)} leads).
      </p>
      <Reliability bins={m.reliability} title={name} />
      <dl className={s.facts}>
        <div>
          <dt>Calibration error</dt>
          <dd>{fixed(m.test.ece, 3)}</dd>
        </div>
        <div>
          <dt>Before calibration</dt>
          <dd>{fixed(m.test_uncalibrated.ece, 3)}</dd>
        </div>
        <div>
          <dt>Ranking (AUC)</dt>
          <dd>{fixed(m.test.auc, 3)}</dd>
        </div>
        <div>
          <dt>Base rate</dt>
          <dd>{share(m.test.base_rate, 1)}</dd>
        </div>
      </dl>
    </article>
  );
}

export function Models({ study }: { study: Study }) {
  const ms = study.prepare.models;
  return (
    <div className={s.grid}>
      <ModelCard name="contact" m={ms.contact} />
      <ModelCard name="win" m={ms.win} />
    </div>
  );
}
