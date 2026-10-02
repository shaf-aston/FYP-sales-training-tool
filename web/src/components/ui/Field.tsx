"use client";

import {
  useId,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import s from "./Field.module.css";

interface Wrap {
  label: string;
  hideLabel?: boolean;
  hint?: ReactNode;
  /** Shows "n / max" when the control has a maxLength. */
  count?: number;
}

function Frame({ id, label, hideLabel, hint, count, max, children }: Wrap & { id: string; max?: number; children: ReactNode }) {
  const showCount = max !== undefined && count !== undefined;
  const ratio = showCount ? count / max : 0;
  return (
    <div className={s.field}>
      <label htmlFor={id} className={hideLabel ? "sr-only" : s.label}>
        {label}
      </label>
      {children}
      {(hint || showCount) && (
        <div className={s.meta}>
          {hint && <span id={`${id}-hint`}>{hint}</span>}
          {showCount && (
            <span className={ratio >= 1 ? s.over : ratio > 0.9 ? s.warn : undefined}>
              {count} / {max}
            </span>
          )}
        </div>
      )}
    </div>
  );
}

export function TextInput({ label, hideLabel, hint, ...rest }: Wrap & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId();
  return (
    <Frame id={id} label={label} hideLabel={hideLabel} hint={hint}>
      <input id={id} className={s.control} aria-describedby={hint ? `${id}-hint` : undefined} {...rest} />
    </Frame>
  );
}

export function TextArea({ label, hideLabel, hint, count, ...rest }: Wrap & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId();
  return (
    <Frame id={id} label={label} hideLabel={hideLabel} hint={hint} count={count} max={rest.maxLength}>
      <textarea id={id} className={s.control} aria-describedby={hint ? `${id}-hint` : undefined} {...rest} />
    </Frame>
  );
}

export function Select({ label, hideLabel, hint, children, ...rest }: Wrap & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId();
  return (
    <Frame id={id} label={label} hideLabel={hideLabel} hint={hint}>
      <select id={id} className={s.control} {...rest}>
        {children}
      </select>
    </Frame>
  );
}

/** On/off switch with a visible label. */
export function Switch({ label, checked, onChange }: { label: string; checked: boolean; onChange: (on: boolean) => void }) {
  return (
    <button type="button" role="switch" aria-checked={checked} className={s.switchRow} onClick={() => onChange(!checked)}>
      <span>{label}</span>
      <span className={`${s.switch} ${checked ? s.switchOn : ""}`} aria-hidden="true" />
    </button>
  );
}

/** One-of-many choice shown as joined buttons, e.g. Easy / Medium / Hard. */
export function Segmented<V extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string;
  options: { value: V; label: string }[];
  value: V;
  onChange: (v: V) => void;
}) {
  const id = useId();
  return (
    <div className={s.field}>
      <span className={s.label} id={id}>
        {label}
      </span>
      <div className={s.segmented} role="group" aria-labelledby={id}>
        {options.map((o) => (
          <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}>
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}
