"use client";

import { Card, Eyebrow } from "@/components/ui";
import { stageMeta } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import s from "./StageCard.module.css";

/** Buy mode: the stage the AI seller has reached. */
export function StageCard() {
  const { stage } = useSession();
  const label = stageMeta(stage).label;

  return (
    <Card tone="accent" className={s.card} aria-label="Stage of the sale">
      <Eyebrow>Stage</Eyebrow>
      <p key={label} className={s.stageName} aria-live="polite">
        {label}
      </p>
    </Card>
  );
}
