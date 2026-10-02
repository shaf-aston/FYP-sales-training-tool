import type { ReactNode } from "react";
import s from "./Feedback.module.css";

/** The one look for loading, empty and error states everywhere. */
export function Notice({ kind, children, action }: { kind: "loading" | "empty" | "error"; children: ReactNode; action?: ReactNode }) {
  return (
    <div className={`${s.notice} ${s[kind]}`} role={kind === "error" ? "alert" : "status"}>
      {kind === "loading" && <TypingDots />}
      <span>{children}</span>
      {action}
    </div>
  );
}

export function TypingDots({ label }: { label?: string }) {
  return (
    <span className={s.dots} role={label ? "status" : undefined} aria-label={label}>
      <i />
      <i />
      <i />
    </span>
  );
}

/** Five bars that bounce while the coach is talking. Decorative. */
export function VoiceWave() {
  return (
    <span className={s.wave} aria-hidden="true">
      <i />
      <i />
      <i />
      <i />
      <i />
    </span>
  );
}
