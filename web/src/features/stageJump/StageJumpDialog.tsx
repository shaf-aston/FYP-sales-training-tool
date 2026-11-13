"use client";

import { useState } from "react";
import { Button, Dialog, TextButton, TextInput } from "@/components/ui";
import type { StageStart } from "@/lib/api/types";
import { stageShort } from "@/lib/labels";
import s from "./StageJump.module.css";

interface Props {
  /** The stage to jump to; null = closed. */
  target: StageStart | null;
  /** Whose answers the recap shows: "you" when the learner is the prospect (buy), "they" for the AI prospect (sell). */
  speaker: "you" | "they";
  busy: boolean;
  onClose: () => void;
  onStart: (slots: Record<string, string>) => void;
}

/** Before a stage jump: the answers the prospect is taken to have given so far, so the call picks up mid-way.
 *  Read at a glance; "Edit" opens them up. Shared by both modes: only `speaker` differs. */
export function StageJumpDialog({ target, speaker, busy, onClose, onStart }: Props) {
  // Edits belong to the stage they were made for: another stage opens with its own sample answers.
  const [edited, setEdited] = useState<{ step: string; answers: Record<string, string> } | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const recap = target?.recap ?? [];
  const answers =
    edited && edited.step === target?.step ? edited.answers : Object.fromEntries(recap.map((r) => [r.slot, r.answer]));
  const isEditing = !!target && editing === target.step;
  const set = (slot: string, value: string) =>
    target && setEdited({ step: target.step, answers: { ...answers, [slot]: value } });

  return (
    <Dialog
      open={!!target}
      onClose={onClose}
      size="sm"
      title={target ? `Jump to ${stageShort(target.stage)}` : ""}
      actions={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" busy={busy} busyLabel="Starting…" onClick={() => onStart(answers)}>
            Start here
          </Button>
        </>
      }
    >
      <p className={s.lead}>A fresh practice call. This chat is cleared.</p>
      {recap.length > 0 && (
        <section className={s.recap} aria-label="So far">
          <div className={s.head}>
            <span className={s.title}>So far, {speaker} said</span>
            {!isEditing && <TextButton onClick={() => target && setEditing(target.step)}>Edit</TextButton>}
          </div>
          {isEditing ? (
            recap.map((r) => (
              <TextInput
                key={r.slot}
                label={r.question}
                value={answers[r.slot] ?? ""}
                maxLength={200}
                onChange={(e) => set(r.slot, e.target.value)}
              />
            ))
          ) : (
            <dl className={s.list}>
              {recap.map((r) => (
                <div key={r.slot} className={s.row}>
                  <dt>{r.question}</dt>
                  <dd>{answers[r.slot]}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
      )}
    </Dialog>
  );
}
