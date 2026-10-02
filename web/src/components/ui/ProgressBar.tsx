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
        <span className={s.fill} style={{ width: `${Math.max(2, pct)}%` }} />
      </div>
      {caption && <p className={s.caption}>{caption}</p>}
    </div>
  );
}
