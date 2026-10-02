"use client";

import { useEffect } from "react";
import { Button, Dialog } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/features/shell/UiContext";
import { DrillsDialog } from "./DrillsDialog";
import { EvaluationBody } from "./EvaluationCard";
import { evalStore } from "./evalStore";
import { ReviewDialog } from "./ReviewDialog";
import { useEvaluation } from "./useEvaluation";
import s from "./ProspectDialogs.module.css";

/** Mounted once at the root: runs the automatic evaluation and hosts the modal/inline views, review and drills. */
export function ProspectDialogs() {
  const { prospect } = useSession();
  const { dialog, closeDialog } = useUi();
  const { state, run, display } = useEvaluation();
  const sid = prospect?.sessionId ?? null;
  const ended = !!prospect?.ended;

  // A different (or no) prospect session makes the old evaluation stale.
  useEffect(() => {
    if (state.sessionId && state.sessionId !== sid) {
      evalStore.reset();
      if (dialog === "evaluation") closeDialog();
    }
  }, [state.sessionId, sid, dialog, closeDialog]);

  // The buyer ended the conversation: score it once.
  useEffect(() => {
    if (ended && state.sessionId !== sid) run();
  }, [ended, sid, state.sessionId, run]);

  const mine = state.sessionId !== null && state.sessionId === sid;
  const showInline = display === "inline" && mine && state.status !== "idle" && !state.dismissed;

  return (
    <>
      <Dialog open={dialog === "evaluation"} onClose={closeDialog} kicker="Prospect practice" title="How that session went" size="lg">
        {dialog === "evaluation" && <EvaluationBody />}
      </Dialog>
      {showInline && (
        <aside className={s.inline} aria-label="How that session went">
          <div className={s.inlineHead}>
            <h2 className={s.inlineTitle}>How that session went</h2>
            <Button variant="ghost" onClick={evalStore.dismiss}>
              Close
            </Button>
          </div>
          <EvaluationBody />
        </aside>
      )}
      <ReviewDialog />
      <DrillsDialog />
    </>
  );
}
