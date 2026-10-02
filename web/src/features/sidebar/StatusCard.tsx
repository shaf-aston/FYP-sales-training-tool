"use client";

import { Badge, Card, Eyebrow } from "@/components/ui";
import { key, stageMeta, stagesFor, strategyMeta } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import s from "./StatusCard.module.css";

export function StatusCard() {
  const { mode, strategy, stage } = useSession();
  const prospect = mode === "prospect";
  const strat = strategyMeta(prospect ? "prospect" : strategy);
  const stageInfo = stageMeta(stage);
  const steps = prospect ? ["Prospect practice live"] : stagesFor(strategy).map((id) => stageMeta(id).label);
  const ids = stagesFor(strategy).map(key);
  const current = prospect ? 0 : ids.indexOf(key(stage));
  const noteFromStrategy = prospect || key(strategy) === "-" || key(strategy) === "";
  const note = noteFromStrategy ? strat.note : stageInfo.note;

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
      <ol className={s.stepper} aria-label="Stage progress">
        {steps.map((label, i) => {
          const state = i === current ? "current" : i < current ? "done" : "todo";
          return (
            <li key={label} className={`${s.step} ${s[state]}`} aria-current={state === "current" ? "step" : undefined}>
              <span className={s.dot} aria-hidden="true" />
              <span className={s.label}>{label}</span>
              {state === "done" && <span className="sr-only"> (done)</span>}
            </li>
          );
        })}
      </ol>
    </Card>
  );
}
