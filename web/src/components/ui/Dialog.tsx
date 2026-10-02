"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";
import s from "./Dialog.module.css";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  kicker?: string;
  children: ReactNode;
  /** Buttons row at the bottom. */
  actions?: ReactNode;
  size?: "sm" | "md" | "lg";
}

/**
 * Modal built on the native <dialog>: the browser gives focus trapping, Escape,
 * focus restore and the top layer (so it can never render under anything).
 */
export function Dialog({ open, onClose, title, kicker, children, actions, size = "md" }: Props) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (open && !el.open) el.showModal();
    if (!open && el.open) el.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      className={`${s.dialog} ${s[size]}`}
      aria-labelledby={titleId}
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()}
    >
      <div className={s.card}>
        <header className={s.head}>
          <div>
            {kicker && <p className={s.kicker}>{kicker}</p>}
            <h2 id={titleId} className={s.title}>
              {title}
            </h2>
          </div>
          <button type="button" className={s.close} onClick={onClose} aria-label="Close">
            ×
          </button>
        </header>
        <div className={s.body}>{children}</div>
        {actions && <footer className={s.actions}>{actions}</footer>}
      </div>
    </dialog>
  );
}
