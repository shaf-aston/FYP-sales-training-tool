import type { ButtonHTMLAttributes } from "react";
import s from "./Button.module.css";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "pill";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  /** Shows a busy label and blocks clicks while an action runs. */
  busy?: boolean;
  busyLabel?: string;
  /** Toggle buttons: sets aria-pressed and the "on" look. */
  pressed?: boolean;
  block?: boolean;
}

export function Button({ variant = "secondary", busy, busyLabel, pressed, block, className, children, disabled, ...rest }: Props) {
  return (
    <button
      type="button"
      {...rest}
      className={[s.btn, s[variant], block && s.block, pressed && s.on, className].filter(Boolean).join(" ")}
      aria-pressed={pressed}
      aria-busy={busy || undefined}
      disabled={disabled || busy}
    >
      {busy && busyLabel ? busyLabel : children}
    </button>
  );
}
