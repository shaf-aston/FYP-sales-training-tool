import { Icon } from "@/components/ui";
import type { SopElement } from "@/lib/api/types";
import s from "./Sop.module.css";

/** The elements of a good call: covered ones with the SOP step that covers them, missing ones with why they matter. */
export function ElementList({ elements }: { elements: SopElement[] }) {
  return (
    <ul className={s.checklist}>
      {elements.map((e) => (
        <li key={e.id} className={`${s.check} ${e.covered ? "" : s.missing}`}>
          <span className={s.mark} aria-hidden="true">
            {e.covered && <Icon name="check" size={14} />}
          </span>
          <span className={s.checkText}>
            <strong className={s.checkLabel}>
              {e.label}
              <span className="sr-only">{e.covered ? ": covered" : ": missing"}</span>
            </strong>
            {e.covered && e.step ? <q className={s.quote}>{e.step}</q> : <span className={s.why}>{e.why}</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
