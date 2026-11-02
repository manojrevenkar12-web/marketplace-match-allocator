import { fixed, int, ms } from "../../shared/lib/format";
import type { GateCheck, Results } from "../../shared/lib/results";
import s from "./production.module.css";

const shown = (v: GateCheck["actual"]) =>
  v === null ? "not run" : typeof v === "boolean" ? String(v) : Number.isInteger(v) ? int(v) : fixed(v, 3);

function Checks({ rows, kind }: { rows: GateCheck[]; kind: "floor" | "target" }) {
  return (
    <ul className={s.checks}>
      {rows.map((c) => {
        const tone = c.ok ? s.pass : kind === "floor" ? s.fail : s.miss;
        const word = c.ok ? (kind === "floor" ? "Pass" : "Met") : kind === "floor" ? "Fail" : "Missed";
        return (
          <li key={c.name}>
            <span className={`${s.mark} ${tone}`}>{word}</span>
            <span className={s.name}>{c.name}</span>
            <span className={s.actual}>
              {shown(c.actual)} {c.op} {c.value}
            </span>
          </li>
        );
      })}
    </ul>
  );
}

export function Production({ r }: { r: Results }) {
  const st = r.study;
  const sv = r.serving;
  const failed = r.gate?.floors.filter((f) => !f.ok).length ?? 0;
  return (
    <div className={s.grid}>
      {st ? (
        <article className={s.card}>
          <h3>Data foundation</h3>
          <p>dbt builds the training set from raw logs; the online feature store must agree with it exactly.</p>
          <dl className={s.facts}>
            <div>
              <dt>dbt models and tests</dt>
              <dd>
                {int(st.prepare.dbt.nodes)} nodes, {int(st.prepare.dbt.tests)} tests, {int(st.prepare.dbt.failed)} failed
              </dd>
            </div>
            <div>
              <dt>Training rows</dt>
              <dd>{int(st.prepare.training_rows)}</dd>
            </div>
            <div>
              <dt>Training and serving features that disagree</dt>
              <dd>
                {int(st.prepare.parity.mismatches)} of {int(st.prepare.parity.pairs)} leads
              </dd>
            </div>
          </dl>
        </article>
      ) : null}
      {sv ? (
        <article className={s.card}>
          <h3>Serving</h3>
          <p>
            {sv.contention.service_instances} instances on one Postgres, {sv.contention.threads} threads, every partner's volume squeezed to{" "}
            {sv.contention.cap_squeezed_to}. Volume is reserved in the database, so no partner gets more leads than they asked for.
          </p>
          <dl className={s.facts}>
            <div>
              <dt>Leads sent under contention</dt>
              <dd>{int(sv.contention.leads)}</dd>
            </div>
            <div>
              <dt>Leads over a partner's volume</dt>
              <dd>{int(sv.contention.oversold_leads)}</dd>
            </div>
            <div>
              <dt>Retried request, same answer</dt>
              <dd>{sv.contention.retry_returns_same_decision ? "Yes" : "No"}</dd>
            </div>
            <div>
              <dt>Latency with the model, p50 / p95</dt>
              <dd>
                {ms(sv.latency.p50_ms)} / {ms(sv.latency.p95_ms)}
              </dd>
            </div>
          </dl>
        </article>
      ) : null}
      {r.gate ? (
        <article className={`${s.card} ${s.gate}`} data-testid="gate">
          <h3>Release gate</h3>
          <p className={`${s.verdict} ${failed ? s.fail : s.pass}`}>
            {failed
              ? `${failed} of ${r.gate.floors.length} floors failed: this build does not ship.`
              : `All ${r.gate.floors.length} floors pass.`}
          </p>
          <Checks rows={r.gate.floors} kind="floor" />
          <p>Targets are reported, not enforced:</p>
          <Checks rows={r.gate.targets} kind="target" />
        </article>
      ) : null}
    </div>
  );
}
