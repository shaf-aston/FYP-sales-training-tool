"use client";

import { useState } from "react";
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
  const [picked, setPicked] = useState<number | null>(null);
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
  const shown = STAGE_STEPS[picked ?? Math.max(at, 0)];
  const showMeta = stageMeta(shown.id);

  return (
    <Card tone="accent" className={s.card} aria-label="Stage of the sale">
      <Eyebrow>
        Stage {Math.max(at + 1, 1)} of {STAGE_STEPS.length}
      </Eyebrow>
      <p key={label} className={s.stageName} aria-live="polite">
        {label}
      </p>
      <ol className={s.steps} aria-label="All stages">
        {STAGE_STEPS.map((step, i) => (
          <li key={step.id} className={i < at ? s.done : i === at ? s.now : undefined}>
            <button
              type="button"
              className={`${s.step} ${shown.id === step.id ? s.picked : ""}`}
              aria-current={i === at ? "step" : undefined}
              aria-pressed={shown.id === step.id}
              onClick={() => setPicked(picked === i || i === at ? null : i)}
            >
              <span className={s.bar} />
              <span className={s.name}>{step.short}</span>
            </button>
          </li>
        ))}
      </ol>
      <div className={s.detail} aria-live="polite">
        {shown.id !== STAGE_STEPS[Math.max(at, 0)].id && (
          <p className={s.detailTitle}>
            {showMeta.label}
            <span className={s.tag}>{STAGE_STEPS.indexOf(shown) < at ? "Done" : "Coming up"}</span>
          </p>
        )}
        {showMeta.hint && <p className={s.detailText}>{showMeta.hint}</p>}
        {at > 0 && <p className={s.tip}>To go back a stage, edit one of your earlier messages.</p>}
      </div>
    </Card>
  );
}
