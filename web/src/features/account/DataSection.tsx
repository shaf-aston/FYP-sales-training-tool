"use client";

import { useState } from "react";
import { Button, TextInput, useConfirm, useToast } from "@/components/ui";
import { api, ApiError, errorText } from "@/lib/api/client";
import { saveJson } from "@/lib/download";
import { useAccount } from "./AccountContext";
import { forgetSkills } from "./useSkillSync";
import s from "./AccountDialog.module.css";

/** Everything kept for the learner: download it, or delete the account (password, then a danger confirm). */
export function DataSection({ onDeleted }: { onDeleted: () => void }) {
  const { refresh, handleLoggedOut } = useAccount();
  const toast = useToast();
  const confirm = useConfirm();
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const [wrong, setWrong] = useState("");
  const [busy, setBusy] = useState(false);

  const download = async () => {
    setExporting(true);
    try {
      const data = await api.accountExport();
      saveJson(`eloquence-account-${new Date().toISOString().slice(0, 10)}.json`, data);
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't get your data. Try again."), "error");
    } finally {
      setExporting(false);
    }
  };

  const remove = async () => {
    const ok = await confirm({
      title: "Delete your account?",
      body: "Your skill history, saved prospects and team place go for good. This cannot be undone.",
      confirmLabel: "Delete account",
      cancelLabel: "Keep it",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    setWrong("");
    try {
      await api.accountDelete(password);
      forgetSkills();
      await refresh();
      toast("Account deleted.", "success");
      onDeleted();
    } catch (err) {
      if (err instanceof ApiError && err.code === "PASSWORD_WRONG") setWrong(err.message);
      else if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't delete the account. Try again."), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className={s.section} aria-labelledby="account-data">
      <h3 id="account-data" className={s.heading}>
        Your data
      </h3>
      <Button className={s.start} busy={exporting} busyLabel="Preparing…" onClick={download}>
        Download my data
      </Button>
      {deleting ? (
        <div className={s.stack}>
          <TextInput
            label="Your password, to delete the account"
            type="password"
            autoComplete="current-password"
            autoFocus
            value={password}
            hint={wrong && <span className={s.fieldError}>{wrong}</span>}
            aria-invalid={!!wrong || undefined}
            onChange={(e) => setPassword(e.target.value)}
          />
          <div className={s.row}>
            <Button variant="danger" busy={busy} busyLabel="Deleting…" disabled={!password} onClick={remove}>
              Delete account
            </Button>
            <Button variant="ghost" onClick={() => setDeleting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="ghost" className={s.flush} onClick={() => setDeleting(true)}>
          Delete account…
        </Button>
      )}
    </section>
  );
}
