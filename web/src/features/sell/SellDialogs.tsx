"use client";

import { useEffect, useRef } from "react";
import { Button, Dialog } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { DrillsDialog } from "./DrillsDialog";
import { EvaluationBody } from "./EvaluationCard";
import { evalStore } from "./evalStore";
import { ReviewDialog } from "./ReviewDialog";
import { useEvaluation } from "./useEvaluation";
import s from "./SellDialogs.module.css";

/** Mounted once at the root: runs the automatic evaluation and hosts the modal/inline views, review and drills. */
export function SellDialogs() {
  const { sellSession } = useSession();
  const { dialog, closeDialog } = useUi();
  const { state, run } = useEvaluation();
  const sid = sellSession?.sessionId ?? null;
  const ended = !!sellSession?.ended;

  // A different (or no) buyer makes the old evaluation stale.
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

  return (
    <>
      <Dialog open={dialog === "evaluation"} onClose={closeDialog} title="How that session went" size="lg">
        {dialog === "evaluation" && <EvaluationBody />}
      </Dialog>
      <ReviewDialog />
      <DrillsDialog />
    </>
  );
}

/** Evaluation shown as a card at the end of the chat when "Inline" display is chosen. */
export function InlineEvaluation() {
  const { sellSession } = useSession();
  const { state, display } = useEvaluation();
  const ref = useRef<HTMLElement>(null);
  const mine = state.sessionId !== null && state.sessionId === (sellSession?.sessionId ?? null);
  const visible = display === "inline" && mine && state.status !== "idle" && !state.dismissed;

  // Bring the result into view when it arrives at the end of the chat.
  useEffect(() => {
    if (visible) ref.current?.scrollIntoView({ block: "nearest" });
  }, [visible, state.status]);

  if (display !== "inline" || !mine || state.status === "idle" || state.dismissed) return null;
  return (
    <aside ref={ref} className={s.inline} aria-label="How that session went">
      <div className={s.inlineHead}>
        <h2 className={s.inlineTitle}>How that session went</h2>
        <Button variant="ghost" onClick={evalStore.dismiss}>
          Hide
        </Button>
      </div>
      <EvaluationBody />
    </aside>
  );
}
