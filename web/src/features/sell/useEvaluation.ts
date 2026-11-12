"use client";

import { useCallback } from "react";
import { api, errorText } from "@/lib/api/client";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { skillStore } from "@/features/skills/skillStore";
import { evalStore, useEvalState } from "./evalStore";

/** Request and read the end-of-session evaluation. */
export function useEvaluation() {
  const { sellSession, sellSettings, handleExpired, markSellEnded } = useSession();
  const { openDialog } = useUi();
  const state = useEvalState();
  const sid = sellSession?.sessionId;
  const display = sellSettings.evalDisplay;

  const run = useCallback(async () => {
    if (!sid) return;
    evalStore.begin(sid);
    if (display === "modal") openDialog("evaluation");
    try {
      const result = await api.sellEvaluate(sid);
      evalStore.succeed(sid, result);
      markSellEnded(result.outcome);   // "End and score" ends the call: the buyer takes no more turns
      skillStore.recordEvaluation(sid, result);   // Skill Radar keeps every scored session
    } catch (err) {
      if (handleExpired(err)) return;
      evalStore.fail(sid, errorText(err, "Something went wrong while scoring."));
    }
  }, [sid, display, openDialog, handleExpired, markSellEnded]);

  return { state, run, display, forThisSession: state.sessionId !== null && state.sessionId === sid };
}
