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

/** The call's five stages, and a practice call started at any of them (the same recap and dialog in both modes).
 * Buy mode: the stage the AI seller has reached. Sell mode: the stage this practice call started at; the learner
 * moves the call on themselves, so no live stage is claimed.
 * Hidden while the quiz is open, so the quiz never shows its own answer. */
export function StageCard() {
  const { stage, mode, buySessionId, jumpTo, practiceFrom, sellSession, startBuyer } = useSession();
  const { sidePanel } = useUi();
  const [picked, setPicked] = useState<number | null>(null);
  const sell = mode === "sell";
  const jump = useStageJump(
    () =>
      sell
        ? sellSession
          ? api.sellStageStarts(sellSession.productType, sellSession.persona.name).then((r) => r.stages)
          : Promise.resolve([])
        : buySessionId
          ? api.buyStageStarts(buySessionId).then((r) => r.stages)
          : Promise.resolve([]),
    async (to, answers) => {
      const ok = sell
        ? !!sellSession &&
          (await startBuyer(sellSession.difficulty, sellSession.productType, {
            persona: sellSession.persona.name,
            objection: sellSession.pick.objection,
            jump: { stage: to.stage, answers },
          }))
        : await jumpTo(to.step, answers, to.stage);
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
  const label = sell ? (practiceFrom ? `Practice from ${stageShort(practiceFrom)}` : "From the start") : stageMeta(stage).label;
  const at = sell ? Math.max(stageIndex(practiceFrom ?? "intent"), 0) : stageIndex(stage);
  const shown = STAGE_STEPS[picked ?? Math.max(at, 0)];
  const showMeta = stageMeta(shown.id);

  // Click a stage (in buy mode, another one) → recap card of the answers skipped → fresh practice call at that stage's main step.
  const onStage = async (i: number) => {
    if (sell ? !sellSession : i === at || !buySessionId) return setPicked(picked === i || i === at ? null : i);
    await jump.open(STAGE_STEPS[i].id);
  };

  return (
    <Card tone="accent" className={s.card} aria-label="Stage of the sale">
      <Eyebrow>{sell ? "Stages" : `Stage ${Math.max(at + 1, 1)} of ${STAGE_STEPS.length}`}</Eyebrow>
      <p key={label} className={s.stageName} aria-live="polite">
        {label}
      </p>
      {!sell && practiceFrom && (
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
            {!sell && <span className={s.tag}>{STAGE_STEPS.indexOf(shown) < at ? "Done" : "Coming up"}</span>}
          </p>
        )}
        {(sell ? showMeta.sellHint : showMeta.hint) && <p className={s.detailText}>{sell ? showMeta.sellHint : showMeta.hint}</p>}
        <p className={s.tip}>Pick a stage to {sell ? "practise from it" : "jump there"}.</p>
      </div>
      <StageJumpDialog key={jump.key} speaker={sell ? "they" : "you"} {...jump.dialog} />
    </Card>
  );
}
