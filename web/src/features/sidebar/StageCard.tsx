"use client";

import { useState } from "react";
import { Card, Eyebrow, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { STAGE_STEPS, stageIndex, stageMeta } from "@/lib/labels";
import type { StageStart } from "@/lib/api/types";
import { useSession } from "@/features/session/SessionContext";
import { StageJumpDialog } from "./StageJumpDialog";
import { useUi } from "@/state/UiContext";
import s from "./StageCard.module.css";

/** Buy mode: the stage the AI seller has reached, and where it sits in the whole call.
 * Hidden while the quiz is open, so the quiz never shows its own answer. */
export function StageCard() {
  const { stage, mode, buySessionId, jumpTo, practiceFrom } = useSession();
  const toast = useToast();
  const [target, setTarget] = useState<StageStart | null>(null);
  const [starting, setStarting] = useState(false);
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

  // Buy mode: click another stage → recap card of the answers skipped → fresh practice call at that stage's main step.
  const onStage = async (i: number) => {
    if (i === at || mode !== "buy" || !buySessionId) return setPicked(picked === i || i === at ? null : i);
    const want = STAGE_STEPS[i].id;
    const stages = await api.buyStages(buySessionId).then((r) => r.stages).catch(() => null);
    const found = stages?.find((st) => st.stage === want);
    if (!found) return toast(`Couldn't open ${stageMeta(want).label}. Try again.`, "error");
    setTarget(found);
  };

  const onStart = async (slots: Record<string, string>) => {
    if (!target) return;
    setStarting(true);
    const ok = await jumpTo(target.step, slots, target.stage);
    setStarting(false);
    if (ok) {
      setPicked(null);
      setTarget(null);
    }
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
        <span className={s.practice}>Practice · started at {stageMeta(practiceFrom).label}</span>
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
      <StageJumpDialog target={target} busy={starting} onClose={() => setTarget(null)} onStart={(a) => void onStart(a)} />
    </Card>
  );
}
