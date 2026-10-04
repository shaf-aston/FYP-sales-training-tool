"use client";

import { Card, Eyebrow } from "@/components/ui";
import { stageMeta, strategyMeta } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import s from "./StatusCard.module.css";

export function StatusCard() {
  const { mode, stage } = useSession();
  const label = mode === "prospect" ? strategyMeta("prospect").label : stageMeta(stage).label;

  return (
    <Card tone="accent" className={s.card} aria-label="Session status">
      <Eyebrow>Session status</Eyebrow>
      <p key={label} className={s.stageName} aria-live="polite">
        {label}
      </p>
    </Card>
  );
}
