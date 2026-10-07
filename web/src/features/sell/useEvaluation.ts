"use client";

import { useCallback } from "react";
import { api, ApiError } from "@/lib/api/client";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { evalStore, useEvalState } from "./evalStore";

/** Request and read the end-of-session evaluation. */
export function useEvaluation() {
  const { sellSession, sellSettings, handleExpired } = useSession();
  const { openDialog } = useUi();
  const state = useEvalState();
  const sid = sellSession?.sessionId;
  const display = sellSettings.evalDisplay;

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
