"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useConfirm, useToast } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { KnowledgeField } from "@/lib/api/types";
import { briefText, emptyValues, fromData, shortSections, toPayload, type Values } from "./fields";

const reason = (e: unknown) => (e instanceof Error && e.message ? e.message : "Please try again.");

/** Loads, edits, saves and clears the product knowledge. */
export function useKnowledge() {
  const toast = useToast();
  const confirm = useConfirm();
  const [values, setValues] = useState<Values>(emptyValues);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [busy, setBusy] = useState<"save" | "clear" | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError("");
    try {
      const res = await api.knowledge();
      setValues(fromData(res.data ?? {}));
    } catch (e) {
      setLoadError(`Could not load your saved details. ${reason(e)}`);
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
        body: `${thin.join(", ")}. A little more detail makes the practice buyer more realistic. Save anyway?`,
        confirmLabel: "Save anyway",
        cancelLabel: "Keep editing",
      });
      if (!ok) return;
    }
    setBusy("save");
    try {
      await api.saveKnowledge(payload);
      toast("Saved. Reset the chat session to use it.", "success");
    } catch (e) {
      toast(`Could not save. ${reason(e)}`, "error");
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
      await api.clearKnowledge();
      setValues(emptyValues());
      toast("Cleared", "success");
    } catch (e) {
      toast(`Could not clear. ${reason(e)}`, "error");
    } finally {
      setBusy(null);
    }
  };

  return { values, setField, brief, loading, loadError, reload: load, busy, save, clearAll };
}
