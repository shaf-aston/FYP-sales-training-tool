import { axisPoint, labelLines, labelPlace, polygon } from "./radar";
import s from "./SkillRadar.module.css";

const R = 100;        // chart radius in viewBox units
const PAD = 64;       // room for the axis labels (two short lines each)
const LINE = 13;      // label line height
const RINGS = [25, 50, 75, 100];

interface Props {
  axes: { id: string; label: string }[];
  latest: Record<string, number>;
  average: Record<string, number>;
  target: number;
}

/** Each skill on its own axis (0-100): the latest session, the recent average and the target ring. Draws only.
 * A skill the latest session did not measure is drawn at its average, without a dot. */
export function SkillRadar({ axes, latest, average, target }: Props) {
  const n = axes.length;
  const values = (scores: Record<string, number>) => axes.map((a) => scores[a.id]);
  return (
    <svg className={s.radar} viewBox={`${-PAD} ${-PAD / 2} ${2 * (R + PAD)} ${2 * R + PAD}`} role="img"
      aria-label={axes.map((a) => `${a.label} ${latest[a.id] ?? "not scored"}`).join(", ")}>
      {RINGS.map((v) => (
        <polygon key={v} className={s.ring} points={polygon(axes.map(() => v), 100, R)} />
      ))}
      {axes.map((a, i) => {
        const end = axisPoint(i, n, 100, 100, R);
        const label = labelPlace(i, n, R, 12);
        return (
          <g key={a.id}>
            <line className={s.axis} x1={R} y1={R} x2={end.x} y2={end.y} />
            <text className={`${s.label} ${average[a.id] === undefined ? s.unmeasured : ""}`} x={label.x} y={label.y} textAnchor={label.anchor} dominantBaseline="middle">
              {labelLines(average[a.id] === undefined ? `${a.label} (not yet scored)` : a.label).map((line, j, all) => (
                <tspan key={j} x={label.x} dy={j === 0 ? -((all.length - 1) * LINE) / 2 : LINE}>
                  {line}
                </tspan>
              ))}
            </text>
          </g>
        );
      })}
      <polygon className={s.target} points={polygon(axes.map(() => target), 100, R)} />
      <g className={s.grow}>
        <polygon className={s.average} points={polygon(values(average), 100, R)} />
        <polygon className={s.latest} points={polygon(axes.map((a) => latest[a.id] ?? average[a.id]), 100, R)} />
        {axes.map((a, i) => {
          if (latest[a.id] === undefined) return null;
          const p = axisPoint(i, n, latest[a.id], 100, R);
          return <circle key={a.id} className={s.dot} cx={p.x} cy={p.y} r={3.5} />;
        })}
      </g>
    </svg>
  );
}

/** A small trend line for one skill's scores (0-100), newest on the right. */
export function Sparkline({ values }: { values: number[] }) {
  const w = 72;
  const h = 22;
  if (values.length < 2) return <span className={s.sparkEmpty} aria-hidden="true" />;
  const step = w / (values.length - 1);
  const points = values.map((v, i) => `${Math.round(i * step * 10) / 10},${Math.round((h - (v / 100) * h) * 10) / 10}`).join(" ");
  return (
    <svg className={s.spark} viewBox={`0 0 ${w} ${h}`} aria-hidden="true">
      <polyline points={points} />
    </svg>
  );
}
