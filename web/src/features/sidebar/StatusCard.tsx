"use client";

import { useState } from "react";
import { Badge, Card, Eyebrow, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { key, stageMeta, stagesFor, strategyMeta } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import s from "./StatusCard.module.css";

export function StatusCard() {
  const { mode, strategy, stage, flowControls, sessionId, applyBotState, handleExpired } = useSession();
  const toast = useToast();
  const [moving, setMoving] = useState<string | null>(null);
  const prospect = mode === "prospect";
  const strat = strategyMeta(prospect ? "prospect" : strategy);
  const stageInfo = stageMeta(stage);
  const ids = prospect ? ["prospect"] : stagesFor(strategy).map(key);
  const current = prospect ? 0 : ids.indexOf(key(stage));
  const noteFromStrategy = prospect || key(strategy) === "-" || key(strategy) === "";
  const note = noteFromStrategy ? strat.note : stageInfo.note;
  // Steps are buttons only where the server lets the learner move the stage.
  const canJump = !prospect && flowControls && !!sessionId;

  const jump = async (id: string) => {
    if (!sessionId || moving) return;
    setMoving(id);
    try {
      applyBotState(await api.setStage(sessionId, id));
      toast(`Moved to ${stageMeta(id).label}`, "success");
    } catch (e) {
      if (!handleExpired(e)) toast(e instanceof Error && e.message ? e.message : "Couldn't move to that stage.", "error");
    } finally {
      setMoving(null);
    }
  };

  return (
    <Card tone="accent" className={s.card} aria-label="Session status">
      <Eyebrow>Session status</Eyebrow>
      <div className={s.badges}>
        <Badge tone="accent">{strat.label}</Badge>
      </div>
      <div key={prospect ? "p" : stage} className={s.stage} aria-live="polite">
        <p className={s.caption}>Current stage</p>
        <p className={s.stageName}>{prospect ? "Prospect practice" : stageInfo.label}</p>
        <p className={s.note}>{note}</p>
      </div>
      <ol className={s.stepper} aria-label={canJump ? "Stage progress - pick a stage to jump to it" : "Stage progress"}>
        {ids.map((id, i) => {
          const state = i === current ? "current" : i < current ? "done" : "todo";
          const label = prospect ? "Prospect practice live" : stageMeta(id).label;
          const body = (
            <>
              <span className={s.dot} aria-hidden="true" />
              <span className={s.label}>{label}</span>
              {state === "done" && <span className="sr-only"> (done)</span>}
            </>
          );
          return (
            <li key={id} className={`${s.step} ${s[state]}`} aria-current={state === "current" ? "step" : undefined}>
              {canJump && state !== "current" ? (
                <button type="button" className={s.jump} onClick={() => jump(id)} disabled={moving !== null} aria-busy={moving === id || undefined}>
                  {body}
                </button>
              ) : (
                body
              )}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
