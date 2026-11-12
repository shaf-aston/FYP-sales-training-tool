import { Badge, Icon } from "@/components/ui";
import type { SopCheckRes, SopStepResult } from "@/lib/api/types";
import { Critique } from "./Critique";
import { ScoreTile } from "./ScoreTile";
import s from "./Sop.module.css";

/** Steps grouped under their stage, in SOP order. */
function byStage(steps: SopStepResult[]): [string, SopStepResult[]][] {
  const groups = new Map<string, SopStepResult[]>();
  for (const st of steps) groups.set(st.stage, [...(groups.get(st.stage) ?? []), st]);
  return [...groups];
}

/** How a real call followed the SOP: the share of steps heard, whether in order, and each step with where it was said. */
export function StepResults({ result }: { result: SopCheckRes }) {
  const heard = result.steps.filter((st) => st.done).length;
  // The score counts the steps that apply: an "If they…" step the call never needed is left out of it.
  const counted = result.steps.filter((st) => st.done || !st.conditional).length;
  return (
    <div className={s.stack}>
      <p className="sr-only" role="status">
        Call checked: {heard} of {counted} steps heard{result.in_order ? ", in order" : ", out of order"}.
      </p>
      <Critique text={result.critique} />
      <div className={s.split}>
        <ScoreTile value={result.score} label="of the SOP's steps heard">
          <div className={s.row}>
            {result.in_order ? <Badge tone="success">In order</Badge> : <Badge tone="warning">Steps happened out of order</Badge>}
          </div>
          <p className={s.muted}>
            {heard} of {counted} steps{counted < result.steps.length ? `; ${result.steps.length - counted} "if they…" not counted` : ""}
          </p>
          <p className={s.muted}>Rep: {result.rep}</p>
        </ScoreTile>
        <div className={s.stages}>
          {byStage(result.steps).map(([stage, steps]) => (
            <section key={stage} className={s.stageResult}>
              <h4 className={s.label}>{stage}</h4>
              <ul className={s.checklist}>
                {steps.map((st) => (
                  <li key={st.step} className={`${s.check} ${st.done || st.conditional ? "" : s.missing}`}>
                    <span className={s.mark} aria-hidden="true">
                      {st.done && <Icon name="check" size={14} />}
                    </span>
                    <span className={s.checkText}>
                      <span className={s.checkLabel}>{st.step}</span>
                      {st.done ? (
                        <span className={s.said}>
                          <Badge tone="accent">Turn {st.turn}</Badge>
                          <q className={s.quote}>{st.said}</q>
                        </span>
                      ) : (
                        <span className={s.why}>{st.conditional ? "Not heard (only counts if it came up)" : "Not heard"}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
