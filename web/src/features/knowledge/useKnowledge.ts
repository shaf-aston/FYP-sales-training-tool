"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useConfirm, useToast } from "@/components/ui";
import { api, ApiError, errorText } from "@/lib/api/client";
import type { KnowledgeField } from "@/lib/api/types";
import { briefText, emptyValues, fromData, shortSections, toPayload, type Values } from "./fields";
import { readLocalKnowledge, writeLocalKnowledge } from "./knowledgeStore";

/** Where the details are kept: on the account when signed in, else only in this browser. */
export type KnowledgeHome = "account" | "device";

/** Loads, edits, saves and clears the learner's product details. Every new sell call sends this browser's copy. */
export function useKnowledge() {
  const toast = useToast();
  const confirm = useConfirm();
  const [values, setValues] = useState<Values>(emptyValues);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState<"save" | "clear" | null>(null);
  const [home, setHome] = useState<KnowledgeHome>("device");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    const local = readLocalKnowledge();
    try {
      const res = await api.knowledge();
      // The account's copy wins; details typed before signing in are kept until saved to it.
      const data = res.data && Object.keys(res.data).length ? res.data : local;
      writeLocalKnowledge(data);
      setValues(fromData(data));
      setHome("account");
    } catch (e) {
      if (e instanceof ApiError && e.loginRequired) {
        setValues(fromData(local));
        setHome("device");
      } else setLoadError(`Could not load your saved details. ${errorText(e, "Please try again.")}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-off fetch on mount
    void load();
  }, [load]);

  const setField = useCallback((id: KnowledgeField, v: string) => setValues((cur) => ({ ...cur, [id]: v })), []);

  const payload = useMemo(() => toPayload(values), [values]);
  const brief = useMemo(() => briefText(payload), [payload]);

  const save = async () => {
    if (!Object.keys(payload).length) {
      toast("Add at least one detail before saving.", "error");
      return;
    }
    const thin = shortSections(payload);
    if (thin.length) {
      const ok = await confirm({
        title: "These sections look very short",
        body: `${thin.join(", ")}. A little more detail makes the buyer more realistic. Save anyway?`,
        confirmLabel: "Save anyway",
        cancelLabel: "Keep editing",
      });
      if (!ok) return;
    }
    setBusy("save");
    try {
      if (home === "account") await api.saveKnowledge(payload);
      writeLocalKnowledge(payload);
      toast(home === "account" ? "Saved to your account. Your next sell call uses it." : "Saved on this device. Your next sell call uses it.", "success");
    } catch (e) {
      toast(`Could not save. ${errorText(e, "Please try again.")}`, "error");
    } finally {
      setBusy(null);
    }
  };

  const clearAll = async () => {
    const ok = await confirm({
      title: "Clear all saved product knowledge?",
      body: "This removes every detail you saved. It cannot be undone.",
      confirmLabel: "Clear all",
      danger: true,
    });
    if (!ok) return;
    setBusy("clear");
    try {
      if (home === "account") await api.clearKnowledge();
      writeLocalKnowledge(null);
      setValues(emptyValues());
      toast("Cleared", "success");
    } catch (e) {
      toast(`Could not clear. ${errorText(e, "Please try again.")}`, "error");
    } finally {
      setBusy(null);
    }
  };

  return { values, setField, brief, home, loading, loadError, reload: load, busy, save, clearAll };
}
