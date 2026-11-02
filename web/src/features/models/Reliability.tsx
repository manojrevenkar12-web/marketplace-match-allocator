import { fixed, share } from "../../shared/lib/format";
import type { ReliabilityBin } from "../../shared/lib/results";
import { calibrationChart } from "../../shared/theme/tokens";
import s from "./models.module.css";

/** Predicted against observed rate per bin; on the dashed diagonal the probabilities can be taken at face value. */
export function Reliability({ bins, title }: { bins: ReliabilityBin[]; title: string }) {
  const { size, pad, dot } = calibrationChart;
  const inner = size - 2 * pad;
  const lo = Math.max(0, Math.floor(Math.min(...bins.flatMap((b) => [b.predicted, b.observed])) * 10) / 10);
  const hi = Math.min(1, Math.ceil(Math.max(...bins.flatMap((b) => [b.predicted, b.observed])) * 10) / 10);
  const span = hi - lo || 1;
  const x = (v: number) => pad + ((v - lo) / span) * inner;
  const y = (v: number) => size - pad - ((v - lo) / span) * inner;
  const ticks = [lo, lo + span / 2, hi];
  const path = bins.map((b, i) => `${i ? "L" : "M"}${x(b.predicted).toFixed(1)},${y(b.observed).toFixed(1)}`).join("");
  return (
    <svg className={s.svg} viewBox={`0 0 ${size} ${size}`} role="img" aria-labelledby={`${title}-t ${title}-d`}>
      <title id={`${title}-t`}>Reliability of the {title} model</title>
      <desc id={`${title}-d`}>{bins.map((b) => `predicted ${share(b.predicted, 0)}, observed ${share(b.observed, 0)}`).join("; ")}</desc>
      <rect className={s.frame} x={pad} y={pad} width={inner} height={inner} />
      {ticks.map((t) => (
        <g key={t}>
          <line className={s.gridline} x1={x(t)} x2={x(t)} y1={pad} y2={size - pad} />
          <line className={s.gridline} x1={pad} x2={size - pad} y1={y(t)} y2={y(t)} />
          <text x={x(t)} y={size - pad + 16} textAnchor="middle">
            {fixed(t, 2)}
          </text>
          <text x={pad - 6} y={y(t) + 4} textAnchor="end">
            {fixed(t, 2)}
          </text>
        </g>
      ))}
      <line className={s.diagonal} x1={x(lo)} y1={y(lo)} x2={x(hi)} y2={y(hi)} />
      <path className={s.line} d={path} />
      {bins.map((b) => (
        <circle key={b.predicted} className={s.point} cx={x(b.predicted)} cy={y(b.observed)} r={dot} />
      ))}
      <text x={size / 2} y={size - 6} textAnchor="middle">
        Predicted
      </text>
      <text x={12} y={size / 2} textAnchor="middle" transform={`rotate(-90 12 ${size / 2})`}>
        Observed
      </text>
    </svg>
  );
}
