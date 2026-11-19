"use client";

import { CallResult } from "./CallResult";
import { CallSource } from "./CallSource";
import { SavedProspects } from "./SavedProspects";
import { useCallReader } from "./useCallReader";
import s from "./CallImport.module.css";

interface Props {
  /** Runs after the buyer from the call starts. */
  onStarted?: () => void;
  /** Shown with a live buyer: close the form without changing anything. */
  onCancel?: () => void;
}

/** Sell mode, "From a real call": a saved prospect, or bring in a transcript, then practise against that prospect or review the call. */
export function CallImport({ onStarted, onCancel }: Props) {
  const reader = useCallReader();
  const { result, draft } = reader;
  if (!result || !draft)
    return (
      <div className={s.stack}>
        <SavedProspects onStarted={onStarted} />
        <CallSource reader={reader} onCancel={onCancel} />
      </div>
    );
  return <CallResult reader={reader} result={result} draft={draft} onStarted={onStarted} onCancel={onCancel} />;
}
