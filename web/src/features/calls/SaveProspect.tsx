"use client";

import { useState } from "react";
import { Button, useToast } from "@/components/ui";
import { useAccount } from "@/features/account/AccountContext";
import { api, errorText } from "@/lib/api/client";
import type { CustomBuyer } from "@/lib/api/types";

/** Logged in: keep this prospect to practise against again (listed under "From a real call"). */
export function SaveProspect({ buyer }: { buyer: CustomBuyer }) {
  const { user, handleLoggedOut } = useAccount();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  /** The prospect as last saved, so "Saved" shows until it is edited again. */
  const [saved, setSaved] = useState("");
  const current = JSON.stringify(buyer);

  if (!user) return null;

  const save = async () => {
    setSaving(true);
    try {
      await api.accountSaveProspect(buyer);
      setSaved(current);
      toast(`Saved ${buyer.name}. Find them under "From a real call".`, "success");
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't save the prospect. Try again."), "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Button variant="ghost" busy={saving} busyLabel="Saving…" disabled={!buyer.name || saved === current} onClick={save}>
      {saved === current ? "Saved" : "Save prospect"}
    </Button>
  );
}
