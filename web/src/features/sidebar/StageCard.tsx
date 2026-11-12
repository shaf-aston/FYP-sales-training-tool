"use client";

import { useState } from "react";
import { Card, Eyebrow, useConfirm } from "@/components/ui";
import { api } from "@/lib/api/client";
import { STAGE_STEPS, stageIndex, stageMeta } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import s from "./StageCard.module.css";

/** Buy mode: the stage the AI seller has reached, and where it sits in the whole call.
 * Hidden while the quiz is open, so the quiz never shows its own answer. */
export function StageCard() {
  const { stage, mode, buySessionId, jumpTo } = useSession();
  const confirm = useConfirm();
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

  // Buy mode: click another stage → confirm → fresh call at that stage's first step.
  const onStage = async (i: number) => {
    if (i === at || mode !== "buy" || !buySessionId) return setPicked(picked === i || i === at ? null : i);
    const target = STAGE_STEPS[i];
    const ok = await confirm({
      title: `Jump to ${stageMeta(target.id).label}?`,
      body: "Starts a fresh call at this stage. The current chat is cleared.",
      confirmLabel: "Jump",
      cancelLabel: "Stay",
    });
    if (!ok) return;
    const { steps } = await api.buySteps(buySessionId).catch(() => ({ steps: [] }));
    const first = steps.find((st) => st.stage === target.id);
    if (first) await jumpTo(first.id);
  };

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
    </Card>
  );
}
