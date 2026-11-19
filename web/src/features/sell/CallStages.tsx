import { Badge, type Tone } from "@/components/ui";
import type { CallStage, StageStatus } from "@/lib/api/types";
import s from "./CallStages.module.css";

const LABEL: Record<StageStatus, [string, Tone]> = {
  strong: ["Done well", "success"],
  partly: ["Part way", "warning"],
  early: ["Too early", "warning"],
  weak: ["Pushed back", "danger"],
  missed: ["Missed", "danger"],
  none: ["Didn't come up", "neutral"],
};

const turnsText = (turns: number[]) => (turns.length ? `${turns.length > 1 ? "Turns" : "Turn"} ${turns.join(", ")}` : "");

/** The call stage by stage (what was found out, how deep, in what order), with the reason each stage matters and
 *  the one to work on next. Shared by the practice review and a real call's review. */
export function CallStages({ stages, focus }: { stages: CallStage[]; focus?: string | null }) {
  if (!stages.length) return null;
  const next = stages.find((st) => st.id === focus);
  return (
    <section className={s.stages} aria-label="The call, stage by stage">
      <h3 className={s.heading}>The call, stage by stage</h3>
      {next && (
        <div className={s.focus}>
          <p className={s.focusHead}>
            Work on next: <strong>{next.name}</strong>
          </p>
          <p>{next.says}</p>
          <p className={s.why}>{next.why}</p>
          <p className={s.try}>{next.next}</p>
        </div>
      )}
      <ol className={s.list}>
        {stages.map((st) => {
          const [label, tone] = LABEL[st.status];
          return (
            <li key={st.id} className={s.stage}>
              <details>
                <summary className={s.row}>
                  <span className={s.name}>{st.name}</span>
                  <Badge tone={tone}>{label}</Badge>
                  <span className={s.turns}>{turnsText(st.turns)}</span>
                </summary>
                <div className={s.detail}>
                  <p>{st.says}</p>
                  <p className={s.why}>{st.why}</p>
                  {st.next && <p className={s.try}>{st.next}</p>}
                </div>
              </details>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
