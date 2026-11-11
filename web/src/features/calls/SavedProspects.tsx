"use client";

import { useEffect, useId, useState } from "react";
import { Button, TextButton, useConfirm, useToast } from "@/components/ui";
import { useAccount } from "@/features/account/AccountContext";
import { useSession } from "@/features/session/SessionContext";
import { GENERAL_PRODUCT } from "@/features/sell/options";
import { api, errorText } from "@/lib/api/client";
import type { CustomBuyer, SavedProspect } from "@/lib/api/types";
import { config } from "@/lib/config";
import { useUi } from "@/state/UiContext";
import s from "./SavedProspects.module.css";

/** The buyer /api/sell/init takes: the server leaves blank fields out of a saved prospect. */
const buyerOf = ({ profile: p }: SavedProspect): CustomBuyer => ({
  name: p.name,
  background: p.background ?? "",
  personality: p.personality ?? "",
  budget: p.budget ?? "",
  needs: p.needs ?? [],
  pain_points: p.pain_points ?? [],
  objections: p.objections ?? [],
});

function SavedList({ userId, onStarted }: { userId: number; onStarted?: () => void }) {
  const { handleLoggedOut } = useAccount();
  const { startBuyer } = useSession();
  const toast = useToast();
  const confirm = useConfirm();
  const titleId = useId();
  const [list, setList] = useState<SavedProspect[]>([]);
  const [all, setAll] = useState(false);
  const [starting, setStarting] = useState<number | null>(null);

  useEffect(() => {
    let live = true;
    api
      .accountProspects()
      .then((r) => live && setList(r.prospects))
      .catch((err) => live && handleLoggedOut(err));
    return () => {
      live = false;
    };
  }, [userId, handleLoggedOut]);

  if (!list.length) return null;

  const practise = async (p: SavedProspect) => {
    setStarting(p.id);
    const ok = await startBuyer(config.savedProspectDifficulty, GENERAL_PRODUCT, { custom: buyerOf(p) });
    setStarting(null);
    if (ok) onStarted?.();
  };

  const remove = async (p: SavedProspect) => {
    const ok = await confirm({
      title: `Delete ${p.name}?`,
      body: "You can save them again from the call.",
      confirmLabel: "Delete",
      cancelLabel: "Keep",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.accountDeleteProspect(p.id);
      setList((l) => l.filter((x) => x.id !== p.id));
      toast(`Deleted ${p.name}.`, "success");
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't delete that prospect. Try again."), "error");
    }
  };

  const shown = all ? list : list.slice(0, config.calls.savedShown);
  return (
    <section className={s.saved} aria-labelledby={titleId}>
      <h3 id={titleId} className={s.label}>
        Saved prospects
      </h3>
      <ul className={s.list}>
        {shown.map((p) => (
          <li key={p.id} className={s.item}>
            <span className={s.text}>
              <strong className={s.name}>{p.name}</strong>
              {p.profile.background && <span className={s.line}>{p.profile.background}</span>}
            </span>
            <Button busy={starting === p.id} busyLabel="Starting…" disabled={starting !== null} onClick={() => practise(p)}>
              Practise
            </Button>
            <button type="button" className={s.remove} aria-label={`Delete ${p.name}`} disabled={starting !== null} onClick={() => remove(p)}>
              ×
            </button>
          </li>
        ))}
      </ul>
      {list.length > shown.length && (
        <Button variant="ghost" className={s.more} onClick={() => setAll(true)}>
          Show all {list.length}
        </Button>
      )}
    </section>
  );
}

/** "From a real call", above the upload: the learner's saved prospects (logged in), or a nudge to log in. */
export function SavedProspects({ onStarted }: { onStarted?: () => void }) {
  const { ready, user } = useAccount();
  const { openDialog } = useUi();
  if (!ready) return null;
  if (!user)
    return (
      <p className={s.nudge}>
        <TextButton onClick={() => openDialog("account")}>Log in</TextButton>{" "}
        to save prospects and keep your progress.
      </p>
    );
  return <SavedList userId={user.id} onStarted={onStarted} />;
}
