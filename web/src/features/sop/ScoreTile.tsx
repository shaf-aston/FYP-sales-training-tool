"use client";

import type { ReactNode } from "react";
import { ProgressBar } from "@/components/ui";
import { useCountUp } from "@/lib/useCountUp";
import s from "./Sop.module.css";

/** A big percentage that counts up, its bar, and what it measures. */
export function ScoreTile({ value, label, children }: { value: number; label: string; children?: ReactNode }) {
  const shown = useCountUp(value);
  return (
    <div className={s.tile}>
      <p className={s.big} aria-hidden="true">
        {shown}%
      </p>
      <ProgressBar value={value} label={label} />
      <p className={s.tileLabel}>
        <span className="sr-only">{value}% </span>
        {label}
      </p>
      {children}
    </div>
  );
}
