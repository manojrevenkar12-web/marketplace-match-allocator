import { eur, int, lift, pp, share } from "../../shared/lib/format";
import { label, policyLabel } from "../../shared/lib/labels";
import type { PolicyStats, Study } from "../../shared/lib/results";
import s from "./frontier.module.css";

type Col = { key: keyof PolicyStats; head: string; show: (v: number) => string; relative: boolean; judged: boolean };

const cols: Col[] = [
  { key: "matched", head: "Requests matched", show: (v) => share(v), relative: false, judged: true },
  { key: "project", head: "Projects won per request", show: (v) => share(v, 2), relative: true, judged: true },
  { key: "revenue", head: "Lead revenue per request", show: (v) => eur(v, 1), relative: true, judged: true },
  { key: "partner_profit_per_lead", head: "Partner profit per lead", show: (v) => eur(v, 1), relative: true, judged: true },
  { key: "leads", head: "Leads sent", show: (v) => int(v), relative: true, judged: false },
];

const notes: Record<string, string> = {
  rules: "Partner with the lowest share of monthly volume used goes first",
  balanced: "Default: revenue, homeowner and partner outcomes weighted 1, 1, 0.5",
  balanced_without_pacing: "Same weights, but no price on scarce partner volume",
};

/** Same requests, same partners, one policy at a time: what each weighting gives and gives up. */
export function Frontier({ study }: { study: Study }) {
  const base = study.frontier.rules;
  const names = Object.keys(study.frontier);
  return (
    <div className={s.wrap} role="region" aria-label="Policies compared on the same requests" tabIndex={0}>
      <table className={s.table}>
        <caption className={s.caption}>
          {int(base.requests)} requests of one month, every policy run on the same requests and partner volume. Changes are against the
          current rules; matched is in percentage points.
        </caption>
        <thead>
          <tr>
            <th scope="col">Policy</th>
            {cols.map((c) => (
              <th key={c.key} scope="col">
                {c.head}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const p = study.frontier[n];
            const isBase = n === "rules";
            return (
              <tr key={n} className={isBase ? s.base : n === "balanced" ? s.pick : undefined} data-testid={`policy-${n}`}>
                <th scope="row">
                  <span className={s.policy}>{label(policyLabel, n)}</span>
                  {notes[n] ? <span className={s.note}>{notes[n]}</span> : null}
                </th>
                {cols.map((c) => {
                  const v = p[c.key];
                  const d = c.relative ? v / base[c.key] - 1 : v - base[c.key];
                  const tone = !c.judged || Math.abs(d) < 0.005 ? s.flat : d > 0 ? s.up : s.down;
                  return (
                    <td key={c.key}>
                      <span className={s.value}>{c.show(v)}</span>
                      {isBase ? null : <span className={`${s.delta} ${tone}`}>{c.relative ? lift(d) : pp(d, 1)}</span>}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
