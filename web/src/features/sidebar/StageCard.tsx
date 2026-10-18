"use client";

import { Card, Eyebrow } from "@/components/ui";
import { STAGE_STEPS, stageIndex, stageMeta } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import s from "./StageCard.module.css";

/** Buy mode: the stage the AI seller has reached, and where it sits in the whole call.
 * Hidden while the quiz is open, so the quiz never shows its own answer. */
export function StageCard() {
  const { stage } = useSession();
  const { sidePanel } = useUi();
  if (sidePanel === "quiz") {
    return (
      <Card tone="accent" className={s.card} aria-label="Stage of the sale">
        <Eyebrow>Stage</Eyebrow>
        <p className={s.hidden}>Hidden while you take the quiz.</p>
      </Card>
    );
  }
  const label = stageMeta(stage).label;
  const at = stageIndex(stage);

  return (
    <Card tone="accent" className={s.card} aria-label="Stage of the sale">
      <Eyebrow>
        Stage {Math.max(at + 1, 1)} of {STAGE_STEPS.length}
      </Eyebrow>
      <p key={label} className={s.stageName} aria-live="polite">
        {label}
      </p>
      <ol className={s.steps}>
        {STAGE_STEPS.map((step, i) => (
          <li
            key={step.id}
            title={step.short}
            className={i < at ? s.done : i === at ? s.now : undefined}
            aria-current={i === at ? "step" : undefined}
          >
            <span className={s.bar} />
            <span className={s.name}>{step.short}</span>
          </li>
        ))}
      </ol>
    </Card>
  );
}
