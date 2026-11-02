import { fixed, pp, share } from "../../shared/lib/format";
import type { Heldout as HeldoutData } from "../../shared/lib/results";
import s from "./heldout.module.css";

const counted = (share_: number, n: number) => Math.round(share_ * n);

export function lead(h: HeldoutData): string {
  const sm = h.summary;
  const n = sm.scenarios;
  const won = counted(sm.project_lift_share, n);
  return [
    `The model won more projects than the current rules in ${won === n ? `all ${n}` : `${won} of ${n}`} markets,`,
    `with revenue at least ${share(sm.min_revenue_ratio, 1)} of the rules'.`,
    `The budget split's interval held the true effect in ${counted(sm.budget_split_project_covered, n)} of ${n} markets,`,
    `the request split's in ${counted(sm.request_split_project_covered, n)}.`,
  ].join(" ");
}

const title = (name: string) => name.replace(/^\d+[-_]/, "").replaceAll(/[-_]/g, " ");

export function Heldout({ h }: { h: HeldoutData }) {
  const sm = h.summary;
  return (
    <div>
      <div className={s.lead}>
        <span className={`${s.badge} ${h.blind ? "" : s.badgeRerun}`}>
          {h.blind ? `Set ${h.set}, first run, kept as recorded` : `Set ${h.set}, rerun`}
        </span>
        <p>{lead(h)}</p>
      </div>
      {/* biome-ignore lint/a11y/noNoninteractiveTabindex: a table that scrolls sideways must be reachable by keyboard */}
      <section className={s.wrap} aria-label="Held-out markets" tabIndex={0}>
        <table className={s.table}>
          <thead>
            <tr>
              <th scope="col">World</th>
              <th scope="col">What it stresses</th>
              <th scope="col">Projects per request, rules</th>
              <th scope="col">Model</th>
              <th scope="col">Revenue against rules</th>
              <th scope="col">Budget split held the truth</th>
            </tr>
          </thead>
          <tbody>
            {h.results.map((w) => {
              const d = w.model.project - w.rules.project;
              const bs = w.designs.budget_split?.project;
              const t = w.truth.project;
              const held = bs !== undefined && t !== undefined && bs.lo <= t && t <= bs.hi;
              const rev = w.model.revenue / w.rules.revenue;
              return (
                <tr key={w.name} data-testid={`world-${w.name}`}>
                  <th scope="row">{title(w.name)}</th>
                  <td className={s.about}>{w.about}</td>
                  <td>{share(w.rules.project, 2)}</td>
                  <td className={d < 0 ? s.down : undefined}>
                    {share(w.model.project, 2)}
                    <span className={s.delta}>{pp(d)}</span>
                  </td>
                  <td className={rev < 1 ? s.down : undefined}>{fixed(rev, 3)}</td>
                  <td className={held ? s.yes : s.no}>{held ? "Yes" : "No"}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}
