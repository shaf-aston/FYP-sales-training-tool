"use client";

import { CallResult } from "./CallResult";
import { CallSource } from "./CallSource";
import { useCallReader } from "./useCallReader";

interface Props {
  /** Runs after the buyer from the call starts. */
  onStarted?: () => void;
  /** Shown with a live buyer: close the form without changing anything. */
  onCancel?: () => void;
}

/** Sell mode, "From a real call": bring in a transcript, then practise against that prospect or review the call. */
export function CallImport({ onStarted, onCancel }: Props) {
  const reader = useCallReader();
  const { result, draft } = reader;
  if (!result || !draft) return <CallSource reader={reader} onCancel={onCancel} />;
  return <CallResult reader={reader} result={result} draft={draft} onStarted={onStarted} onCancel={onCancel} />;
}
