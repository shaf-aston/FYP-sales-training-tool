import type { SopStage } from "@/lib/api/types";
import s from "./Sop.module.css";

/** The SOP as it was read: each stage folds open to its steps. */
export function SopOutline({ stages }: { stages: SopStage[] }) {
  return (
    <div className={s.outline}>
      {stages.map((st, i) => (
        <details key={`${i}:${st.title}`} className={s.stage}>
          <summary>
            <span>{st.title}</span>
            <span className={s.count}>
              {st.steps.length} {st.steps.length === 1 ? "step" : "steps"}
            </span>
          </summary>
          <ol className={s.steps}>
            {st.steps.map((step, j) => (
              <li key={j}>{step}</li>
            ))}
          </ol>
        </details>
      ))}
    </div>
  );
}
