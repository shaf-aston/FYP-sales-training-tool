"use client";

import { Card, Eyebrow, Notice, Panel } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { AskCoach } from "./AskCoach";
import { cleanCoachText } from "./clean";
import s from "./coach.module.css";

export function CoachPanel() {
  const { coachNotes } = useSession();
  const { closeSidePanel } = useUi();
  const what = cleanCoachText(coachNotes?.what_happened);
  const next = cleanCoachText(coachNotes?.next_move);

  return (
    <Panel title="Coach guidance" onClose={closeSidePanel}>
      <div className={s.stack}>
        {!coachNotes ? (
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
          </div>
        )}
        <AskCoach />
      </div>
    </Panel>
  );
}
