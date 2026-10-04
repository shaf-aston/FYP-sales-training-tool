"use client";

import { useEffect, useState } from "react";
import { Button, Notice, Select, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import { key, stageMeta, strategyMeta } from "@/lib/labels";
import { useSession } from "@/features/session/SessionContext";
import s from "./Sidebar.module.css";

const STRATEGIES = ["consultative", "transactional"];
const errText = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

export function FlowControls() {
  const { flowControls, mode, sessionId, strategy, applyBotState, handleExpired } = useSession();
  const toast = useToast();
  const [pickedStrategy, setPickedStrategy] = useState("");
  const [pickedStage, setPickedStage] = useState("");
  const [stages, setStages] = useState<string[] | null>(null);
  const [busy, setBusy] = useState<"strategy" | "stage" | null>(null);

  // Stages depend on the strategy, so refetch when it changes (reloadTick forces a refetch after Apply).
  const [reloadTick, setReloadTick] = useState(0);
  const active = flowControls && mode === "seller" && !!sessionId;
  useEffect(() => {
    if (!active || !sessionId) return;
    let cancelled = false;
    api
      .stages(sessionId)
      .then((res) => !cancelled && setStages(res.stages))
      .catch((e) => {
        if (cancelled) return;
        setStages([]);
        if (!handleExpired(e)) toast("Couldn't load the stage list.", "error");
      });
    return () => {
      cancelled = true;
    };
  }, [active, sessionId, strategy, reloadTick, handleExpired, toast]);

  if (!flowControls || mode !== "seller") {
    return <Notice kind="empty">Stage and approach controls aren&rsquo;t available in this mode.</Notice>;
  }

  const applyStrategy = async () => {
    if (!sessionId) return toast("Session lost - reconnecting...", "error");
    const target = pickedStrategy || STRATEGIES.find((x) => x !== key(strategy));
    if (!target) return;
    setBusy("strategy");
    try {
      const data = await api.setStrategy(sessionId, target);
      applyBotState(data);
      toast(`Approach set to ${strategyMeta(target).label}`, "success");
      setPickedStage("");
      setReloadTick((n) => n + 1);
    } catch (e) {
      if (!handleExpired(e)) toast(errText(e, "Couldn't change the approach. Try again."), "error");
    } finally {
      setBusy(null);
    }
  };

  const moveStage = async () => {
    if (!sessionId) return toast("Session lost - reconnecting...", "error");
    if (!pickedStage) return toast("Pick a stage first", "info");
    setBusy("stage");
    try {
      const data = await api.setStage(sessionId, pickedStage);
      applyBotState(data);
      toast(`Moved to ${stageMeta(pickedStage).label}`, "success");
    } catch (e) {
      if (!handleExpired(e)) toast(errText(e, "Couldn't move to that stage. Try again."), "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={s.stack}>
      <Select label="Switch strategy" value={pickedStrategy} onChange={(e) => setPickedStrategy(e.target.value)}>
        <option value="">Choose a strategy</option>
        <option value="consultative">Consultative (advice-led)</option>
        <option value="transactional">Transactional (quick sale)</option>
      </Select>
      <Button onClick={applyStrategy} busy={busy === "strategy"} busyLabel="Applying…" disabled={busy !== null} block>
        Apply approach
      </Button>
      {stages === null && <Notice kind="loading">Loading stages...</Notice>}
      <Select
        label="Skip to stage"
        value={pickedStage}
        onChange={(e) => setPickedStage(e.target.value)}
        disabled={!stages?.length}
      >
        <option value="">{stages?.length === 0 ? "No stages available" : "Select stage..."}</option>
        {stages?.map((st) => (
          <option key={st} value={st}>
            {stageMeta(st).label}
          </option>
        ))}
      </Select>
      <Button onClick={moveStage} busy={busy === "stage"} busyLabel="Moving…" disabled={busy !== null} block>
        Move to stage
      </Button>
    </div>
  );
}
