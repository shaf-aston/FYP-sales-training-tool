import s from "./ProgressBar.module.css";

interface Props {
  /** 0..100 */
  value: number;
  label: string;
  /** Visible caption under the bar, e.g. "62% ready". */
  caption?: string;
}

/** Shimmering gradient bar that eases to its new value. */
export function ProgressBar({ value, label, caption }: Props) {
  const pct = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className={s.wrap}>
      <div className={s.track} role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct}>
        {/* the colour is the place on the whole scale: a 35% bar ends amber, only a full one reaches green */}
        <span className={s.fill} style={{ width: `${Math.max(2, pct)}%`, backgroundSize: `${(100 / Math.max(2, pct)) * 100}% 100%` }} />
      </div>
      {caption && <p className={s.caption}>{caption}</p>}
    </div>
  );
}
