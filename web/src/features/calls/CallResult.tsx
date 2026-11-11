"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Notice } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { GENERAL_PRODUCT } from "@/features/sell/options";
import { CallReviewDialog } from "./CallReviewDialog";
import { ProspectCard } from "./ProspectCard";
import { SpeakerPicker } from "./SpeakerPicker";
import { toCustomBuyer, type CallReader, type CallResult as Result, type ProspectDraft } from "./useCallReader";
import s from "./CallResult.module.css";

interface Props {
  reader: CallReader;
  result: Result;
  draft: ProspectDraft;
  onStarted?: () => void;
  onCancel?: () => void;
}

/** Step two: who is who, the editable prospect, then practise against them or review the real call. */
export function CallResult({ reader, result, draft, onStarted, onCancel }: Props) {
  const { startBuyer } = useSession();
  const [starting, setStarting] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const top = useRef<HTMLElement>(null);
  const { call, source } = result;
  // The buyer needs a name (the server refuses one without).
  const name = draft.name.trim();
  const practiseLabel = name ? `Practise against ${name}` : "Name the prospect to practise";

  // The Read button that had focus is gone: start keyboard and screen-reader users at the result (without jumping the panel).
  useEffect(() => top.current?.focus({ preventScroll: true }), []);

  const practise = async () => {
    setReviewing(false);
    setStarting(true);
    const ok = await startBuyer(draft.difficulty, GENERAL_PRODUCT, { custom: toCustomBuyer(draft) });
    setStarting(false);
    if (ok) onStarted?.();
  };

  return (
    <section ref={top} className={s.result} tabIndex={-1} aria-label="The call">
      <SpeakerPicker call={call} busy={reader.busy === "read"} onPick={reader.pickRep} />
      {reader.error && <Notice kind="error">{reader.error}</Notice>}
      <ProspectCard draft={draft} evidence={call.profile.evidence} onEdit={reader.edit} />
      <div className={s.actions}>
        <Button variant="primary" block busy={starting} busyLabel="Starting…" disabled={!!reader.busy || !name} onClick={practise}>
          {practiseLabel}
        </Button>
        <Button block disabled={!!reader.busy} onClick={() => setReviewing(true)}>
          Review the real call
        </Button>
        <div className={s.secondary}>
          <Button variant="ghost" onClick={reader.back}>
            Use another call
          </Button>
          {onCancel && (
            <Button variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
        </div>
      </div>
      <CallReviewDialog
        open={reviewing}
        onClose={() => setReviewing(false)}
        call={source}
        prospect={call.prospect}
        difficulty={draft.difficulty}
        practise={{ label: practiseLabel, onClick: practise, disabled: !name }}
      />
    </section>
  );
}
