"use client";

import { useCallback } from "react";
import { api, ApiError } from "@/lib/api/client";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/features/shell/UiContext";
import { evalStore, useEvalState } from "./evalStore";

/** Request and read the end-of-session evaluation. */
export function useEvaluation() {
  const { prospect, prospectSettings, handleExpired } = useSession();
  const { openDialog } = useUi();
  const state = useEvalState();
  const sid = prospect?.sessionId;
  const display = prospectSettings.evalDisplay;

  const run = useCallback(async () => {
    if (!sid) return;
    evalStore.begin(sid);
    if (display === "modal") openDialog("evaluation");
    try {
      evalStore.succeed(sid, await api.evaluate(sid));
    } catch (err) {
      if (err instanceof ApiError && handleExpired(err)) return;
      evalStore.fail(sid, err instanceof ApiError ? err.message : "Something went wrong while scoring.");
    }
  }, [sid, display, openDialog, handleExpired]);

  return { state, run, display, forThisSession: state.sessionId !== null && state.sessionId === sid };
}
