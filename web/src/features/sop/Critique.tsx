import { Card } from "@/components/ui";
import s from "./Sop.module.css";

/** The written critique: one paragraph the server writes by rules from the result above it (core/sop/critique.py). */
export function Critique({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <Card tone="accent" className={s.critique}>
      <h3 className={s.label}>In short</h3>
      <p>{text}</p>
    </Card>
  );
}
