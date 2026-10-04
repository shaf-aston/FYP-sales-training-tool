"use client";

import { Card, Eyebrow, Notice, Panel } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { AskCoach } from "./AskCoach";
import { cleanCoachText } from "./clean";
import s from "./coach.module.css";

const NO_RISKS = "No risks flagged yet. Keep the buyer talking.";

export function CoachPanel() {
  const { training } = useSession();
  const { closeSidePanel } = useUi();
  const what = cleanCoachText(training?.what_happened);
  const next = cleanCoachText(training?.next_move);
  const risks = (training?.watch_for ?? []).slice(0, 2).map((r) => cleanCoachText(r)).filter(Boolean);

  return (
    <Panel title="Coach guidance" onClose={closeSidePanel}>
      <div className={s.stack}>
        {!training ? (
          <Notice kind="empty">Send your first message and the coach will start guiding you here.</Notice>
        ) : (
          <div aria-live="polite" className={s.stack}>
            {what && (
              <details key={what} className={s.section} open>
                <summary className={s.summary}>What changed</summary>
                <p className={s.text}>{what}</p>
              </details>
            )}
            {next && (
              <Card key={next} tone="accent" className={s.section}>
                <Eyebrow>Next move</Eyebrow>
                <p className={s.next}>{next}</p>
              </Card>
            )}
            <section key={risks.join("|")} className={s.section}>
              <Eyebrow>Watch out</Eyebrow>
              {risks.length ? (
                <ul className={s.list}>
                  {risks.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ul>
              ) : (
                <p className={s.text}>{NO_RISKS}</p>
              )}
            </section>
          </div>
        )}
        <AskCoach />
      </div>
    </Panel>
  );
}
