"use client";

import { useState } from "react";
import { Button, Dialog, TextInput } from "@/components/ui";
import type { StageStart } from "@/lib/api/types";
import { stageMeta } from "@/lib/labels";
import s from "./StageCard.module.css";

interface Props {
  /** The stage to jump to; null = closed. */
  target: StageStart | null;
  busy: boolean;
  onClose: () => void;
  onStart: (slots: Record<string, string>) => void;
}

/** Before a stage jump: the answers taken as given on the stages skipped, which the learner can change.
 *  The seller's first line builds on them, so the call picks up mid-conversation instead of out of nowhere. */
export function StageJumpDialog({ target, busy, onClose, onStart }: Props) {
  // Edits belong to the stage they were made for: another stage opens with its own sample answers.
  const [edited, setEdited] = useState<{ step: string; answers: Record<string, string> } | null>(null);
  const answers =
    edited && edited.step === target?.step
      ? edited.answers
      : Object.fromEntries((target?.recap ?? []).map((r) => [r.slot, r.answer]));
  const setAnswer = (slot: string, value: string) =>
    target && setEdited({ step: target.step, answers: { ...answers, [slot]: value } });
  const label = target ? stageMeta(target.stage).label : "";

  return (
    <Dialog
      open={!!target}
      onClose={onClose}
      title={`Jump to ${label}`}
      actions={
        <>
          <Button onClick={onClose}>Stay</Button>
          <Button variant="primary" busy={busy} busyLabel="Starting…" onClick={() => onStart(answers)}>
            Start here
          </Button>
        </>
      }
    >
      <div className={s.recap}>
        <p className={s.detailText}>
          Starts a fresh practice call at {label}. The current chat is cleared, and practice calls are marked as
          practice.
        </p>
        {target && target.recap.length > 0 ? (
          <>
            <p className={s.detailTitle}>Before {label}, you said</p>
            {target.recap.map((r) => (
              <TextInput
                key={r.slot}
                label={r.question}
                value={answers[r.slot] ?? ""}
                maxLength={200}
                onChange={(e) => setAnswer(r.slot, e.target.value)}
              />
            ))}
            <p className={s.tip}>The rep picks up from these answers. Change any to practise a different buyer.</p>
          </>
        ) : (
          <p className={s.tip}>This is the start of the call, so there is nothing to fill in.</p>
        )}
      </div>
    </Dialog>
  );
}
