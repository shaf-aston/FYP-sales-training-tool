import type { ReactNode } from "react";
import { Button } from "./Button";
import s from "./Notice.module.css";

/** The one look for loading, empty and error states everywhere. `onRetry` adds the "Try again" button. */
export function Notice({ kind, children, onRetry }: { kind: "loading" | "empty" | "error"; children: ReactNode; onRetry?: () => void }) {
  return (
    <div className={`${s.notice} ${s[kind]}`} role={kind === "error" ? "alert" : "status"}>
      {kind === "loading" && <TypingDots />}
      <span>{children}</span>
      {onRetry && (
        <Button variant="ghost" onClick={onRetry}>
          Try again
        </Button>
      )}
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

/** Five bars that bounce while a reply is read aloud. Decorative. */
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
