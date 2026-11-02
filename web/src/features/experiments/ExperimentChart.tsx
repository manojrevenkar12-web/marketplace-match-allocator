import { motion } from "motion/react";
import { int } from "../../shared/lib/format";
import { designLabel, label, metricInfo } from "../../shared/lib/labels";
import type { Metric } from "../../shared/lib/results";
import { linear } from "../../shared/lib/scale";
import { motionTokens } from "../../shared/theme/tokens";
import s from "./experiments.module.css";
import type { DesignRow } from "./model";

interface Props {
  rows: DesignRow[];
  metric: Metric;
}

/** Each design's estimate and 95% interval, drawn against the effect the model really had. */
export function ExperimentChart({ rows, metric }: Props) {
  const info = metricInfo[metric];
  const scale = linear(rows.flatMap((r) => [r.lo, r.hi, r.truth]));
  const step = scale.ticks.length > 1 ? scale.ticks[1] - scale.ticks[0] : 1;
  const digits = Math.max(0, -Math.floor(Math.log10(step * info.tickScale) + 1e-9));
  const truthAt = rows.length ? scale.at(rows[0].truth) : 0;
  return (
    <figure className={s.chart} aria-labelledby="experiments-caption">
      <figcaption id="experiments-caption" className="visually-hidden">
        Estimated effect of the model on {info.unit} by experiment design, with 95% intervals, against the true effect.
      </figcaption>
      <div aria-hidden="true">
        {rows.map((r, i) => {
          const miss = !r.covered;
          return (
            <div className={s.row} key={r.key} data-testid={`design-${r.key}`}>
              <div className={s.label}>
                <span className={s.name}>{label(designLabel, r.key)}</span>
                <span className={s.desc}>{r.description}</span>
                <span className={`${s.hit} ${r.coverage < 0.5 ? s.hitMiss : s.hitOk}`}>
                  Interval held the true effect in {int(r.coverage * r.replications)} of {int(r.replications)} runs
                </span>
              </div>
              <div className={s.track}>
                <div className={s.zero} style={{ left: `${scale.at(0)}%` }} />
                <motion.div className={s.truth} initial={false} animate={{ left: `${truthAt}%` }} transition={motionTokens.change} />
                <motion.div
                  className={`${s.ci} ${miss ? s.ciMiss : ""}`}
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1, left: `${scale.at(r.lo)}%`, width: `${scale.at(r.hi) - scale.at(r.lo)}%` }}
                  transition={{ default: motionTokens.change, scaleX: { ...motionTokens.reveal, delay: i * motionTokens.stagger } }}
                />
                <motion.div
                  className={`${s.dot} ${miss ? s.dotMiss : ""}`}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1, left: `${scale.at(r.estimate)}%` }}
                  transition={{ default: motionTokens.change, opacity: { ...motionTokens.reveal, delay: i * motionTokens.stagger } }}
                />
              </div>
            </div>
          );
        })}
        <div className={s.axis}>
          <span className={s.axisLabel}>Effect on {info.unit}</span>
          <div className={s.axisTrack}>
            {scale.ticks.map((t) => (
              <span key={t} className={s.tick} style={{ left: `${scale.at(t)}%` }}>
                {info.delta(t, digits)}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="visually-hidden">
        <table>
          <caption>Experiment designs: estimate, 95% interval and true effect on {info.unit}</caption>
          <thead>
            <tr>
              <th scope="col">Design</th>
              <th scope="col">Estimate</th>
              <th scope="col">95% interval</th>
              <th scope="col">True effect</th>
              <th scope="col">Runs that covered it</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key}>
                <th scope="row">{label(designLabel, r.key)}</th>
                <td>{info.delta(r.estimate)}</td>
                <td>
                  {info.delta(r.lo)} to {info.delta(r.hi)}
                </td>
                <td>{info.delta(r.truth)}</td>
                <td>
                  {int(r.coverage * r.replications)} of {int(r.replications)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ul className={s.legend}>
        <li>
          <span className={`${s.swatch} ${s.swTruth}`} aria-hidden="true" />
          True effect: model everywhere against rules everywhere
        </li>
        <li>
          <span className={`${s.swatch} ${s.swOk}`} aria-hidden="true" />
          95% interval that holds it
        </li>
        <li>
          <span className={`${s.swatch} ${s.swMiss}`} aria-hidden="true" />
          95% interval that misses it
        </li>
      </ul>
    </figure>
  );
}
