"use client";

import { useState } from "react";
import { Badge, Card, Eyebrow } from "@/components/ui";
import { api } from "@/lib/api/client";
import { STAGE_STEPS, stageIndex, stageMeta, stageShort } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import { StageJumpDialog } from "@/features/stageJump/StageJumpDialog";
import { useStageJump } from "@/features/stageJump/useStageJump";
import { useUi } from "@/state/UiContext";
import s from "./StageCard.module.css";

/** Buy mode: the stage the AI seller has reached, and where it sits in the whole call.
 * Hidden while the quiz is open, so the quiz never shows its own answer. */
export function StageCard() {
  const { stage, mode, buySessionId, jumpTo, practiceFrom } = useSession();
  const { sidePanel } = useUi();
  const [picked, setPicked] = useState<number | null>(null);
  const jump = useStageJump(
    () => (buySessionId ? api.buyStageStarts(buySessionId).then((r) => r.stages) : Promise.resolve([])),
    async (to, slots) => {
      const ok = await jumpTo(to.step, slots, to.stage);
      if (ok) setPicked(null);
      return ok;
    },
  );
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

  // Buy mode: click another stage → recap card of the answers skipped → fresh practice call at that stage's main step.
  const onStage = async (i: number) => {
    if (i === at || mode !== "buy" || !buySessionId) return setPicked(picked === i || i === at ? null : i);
    await jump.open(STAGE_STEPS[i].id);
  };

  return (
    <Card tone="accent" className={s.card} aria-label="Stage of the sale">
      <Eyebrow>
        Stage {Math.max(at + 1, 1)} of {STAGE_STEPS.length}
      </Eyebrow>
      <p key={label} className={s.stageName} aria-live="polite">
        {label}
      </p>
      {mode === "buy" && practiceFrom && (
        <span className={s.practice}>
          <Badge tone="accent">Practice from {stageShort(practiceFrom)}</Badge>
        </span>
      )}
      <ol className={s.steps} aria-label="All stages">
        {STAGE_STEPS.map((step, i) => (
          <li key={step.id} className={i < at ? s.done : i === at ? s.now : undefined}>
            <button
              type="button"
              className={`${s.step} ${shown.id === step.id ? s.picked : ""}`}
              aria-current={i === at ? "step" : undefined}
              aria-pressed={shown.id === step.id}
              onClick={() => void onStage(i)}
              title={i === at ? undefined : `Jump to ${step.short}`}
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
        {mode === "buy" && <p className={s.tip}>Pick a stage to jump there.</p>}
      </div>
      <StageJumpDialog speaker="you" {...jump.dialog} />
    </Card>
  );
}
