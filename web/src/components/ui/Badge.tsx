import type { ReactNode } from "react";
import s from "./Badge.module.css";

export type Tone = "accent" | "success" | "warning" | "danger" | "neutral";

export function Badge({ tone = "neutral", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`${s.badge} ${s[tone]}`}>{children}</span>;
}
