"use client";

import { useState } from "react";
import { useToast } from "@/components/ui";
import type { StageStart } from "@/lib/api/types";

/** The stage-jump flow, apart from where its data comes from: pick a stage → recap → start. Each mode passes
 *  how it lists stage starts and how it starts a call at one; the dialog and its state are the same. */
export function useStageJump(load: () => Promise<StageStart[]>, start: (to: StageStart, slots: Record<string, string>) => Promise<boolean>) {
  const toast = useToast();
  const [target, setTarget] = useState<StageStart | null>(null);
  const [busy, setBusy] = useState(false);

  const open = async (stage: string) => {
    const found = (await load().catch(() => [])).find((st) => st.stage === stage);
    if (found) setTarget(found);
    else toast("Couldn't open that stage. Try again.", "error");
  };

  const onStart = async (slots: Record<string, string>) => {
    if (!target) return;
    setBusy(true);
    const ok = await start(target, slots);
    setBusy(false);
    if (ok) setTarget(null);
  };

  return { open, dialog: { target, busy, onClose: () => setTarget(null), onStart: (a: Record<string, string>) => void onStart(a) } };
}
