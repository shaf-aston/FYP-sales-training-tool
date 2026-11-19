"use client";

// Keeping someone's words past this tab: saved to the learner's account (logged in), or set by a manager as the
// team's, which members' new calls use unless they chose other words. Every change happens in an event handler.

import { useEffect, useId, useState } from "react";
import { Button, TextButton, useConfirm, useToast } from "@/components/ui";
import { useAccount } from "@/features/account/AccountContext";
import { useSession } from "@/features/session/SessionContext";
import { api, errorText } from "@/lib/api/client";
import type { SavedWords, WordsChoice } from "@/lib/api/types";
import { useUi } from "@/state/UiContext";
import { questionCount, whose, wordsTag } from "./words";
import s from "./RepWords.module.css";

/** Just what the server keeps (the session's words carry a `team` flag too). */
const choiceOf = ({ product, label, words, probes }: WordsChoice): WordsChoice => ({ product, label, words, probes });
/** The same choice, whatever order the server kept its steps in. */
const keyOf = (c: WordsChoice) => {
  const sorted = (o: Record<string, string>) => Object.entries(o).sort(([a], [b]) => a.localeCompare(b));
  return JSON.stringify([c.product, c.label, sorted(c.words), sorted(c.probes ?? {})]);
};
/** "12 Nov" from seconds since epoch. */
const savedOn = (seconds: number) => new Date(seconds * 1000).toLocaleDateString(undefined, { day: "numeric", month: "short" });

/** The learner's saved words (newest first), fetched while logged in. */
export function useSavedWords() {
  const { user, handleLoggedOut } = useAccount();
  const [saved, setSaved] = useState<{ userId: number; list: SavedWords[] } | null>(null);
  const userId = user?.id ?? null;

  useEffect(() => {
    if (userId === null) return;
    let live = true;
    api
      .accountWords()
      .then((r) => live && setSaved({ userId, list: r.words }))
      .catch((err) => live && handleLoggedOut(err));
    return () => {
      live = false;
    };
  }, [userId, handleLoggedOut]);

  const list = saved && saved.userId === userId ? saved.list : [];
  return {
    list,
    added: (w: SavedWords) => userId !== null && setSaved({ userId, list: [w, ...list] }),
    removed: (id: number) => userId !== null && setSaved({ userId, list: list.filter((x) => x.id !== id) }),
  };
}

export type SavedWordsState = ReturnType<typeof useSavedWords>;

/** Logged in: keep these questions on the account, to use again. */
export function SaveWords({ choice, saved }: { choice: WordsChoice; saved: SavedWordsState }) {
  const { user, handleLoggedOut } = useAccount();
  const toast = useToast();
  const [saving, setSaving] = useState(false);
  const key = keyOf(choice);
  const done = saved.list.some((w) => keyOf(w) === key);
  if (!user) return null;

  const save = async () => {
    setSaving(true);
    try {
      const res = await api.accountSaveWords(choiceOf(choice));
      saved.added(res.words);
      toast(`Saved ${whose(choice.label)} questions. Find them under "Saved" in Rep's words.`, "success");
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't save those questions. Try again."), "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Button variant="ghost" busy={saving} busyLabel="Saving…" disabled={done} onClick={save}>
      {done ? "Saved" : "Save these questions"}
    </Button>
  );
}

const isTeams = (team: WordsChoice | null, c: WordsChoice) => !!team && keyOf(team) === keyOf(c);

/** A manager: members' new calls on this product use these questions. */
export function UseForTeam({ choice }: { choice: WordsChoice }) {
  const { team, refresh, handleLoggedOut } = useAccount();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  // Already the team's: the team line below says so, with a way to stop them.
  if (team?.role !== "manager" || isTeams(team.words, choice)) return null;

  const set = async () => {
    setBusy(true);
    try {
      await api.teamWords(choiceOf(choice));
      await refresh();
      toast(`Your team's new calls use ${whose(choice.label)} words.`, "success");
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't set your team's words. Try again."), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button variant="ghost" busy={busy} busyLabel="Saving…" onClick={set}>
      Use for my team
    </Button>
  );
}

/** In a team with words: whose they are, a way back to them, and (a manager) a way to stop them. */
export function TeamWords({ starting, onUse }: { starting: boolean; onUse: (w: WordsChoice) => void }) {
  const { team, refresh, handleLoggedOut } = useAccount();
  const { repWords } = useSession();
  const toast = useToast();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const words = team?.words;
  if (!team || !words) return null;
  const manager = team.role === "manager";
  const inUse = !!repWords && isTeams(words, repWords);
  if (inUse && !manager) return null;   // the card above already says this call uses them

  const stop = async () => {
    const ok = await confirm({
      title: "Stop your team's words?",
      body: "Your team's new calls go back to the script's words. Calls already going keep theirs.",
      confirmLabel: "Stop",
      cancelLabel: "Keep",
      danger: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api.teamWords(null);
      await refresh();
      toast("Your team's new calls use the script's words.", "success");
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't stop your team's words. Try again."), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={s.team}>
      <span>
        Your team&apos;s words: {words.label}, {questionCount(Object.keys(words.words).length)}.
        {manager ? " Your team's new calls use them." : ""}
      </span>
      {!inUse && (
        <TextButton disabled={starting || busy} onClick={() => onUse(words)}>
          Use them
        </TextButton>
      )}
      {manager && (
        <TextButton disabled={busy} onClick={stop}>
          {busy ? "Stopping…" : "Stop team words"}
        </TextButton>
      )}
    </div>
  );
}

/** The learner's saved words, each to use or delete; logged out, a hint that logging in keeps them. */
export function SavedWordsList({ saved, starting, onUse }: { saved: SavedWordsState; starting: boolean; onUse: (w: WordsChoice) => void }) {
  const { ready, user, handleLoggedOut } = useAccount();
  const { openDialog } = useUi();
  const toast = useToast();
  const confirm = useConfirm();
  const titleId = useId();
  const [using, setUsing] = useState<number | null>(null);
  if (!ready) return null;
  if (!user)
    return (
      <p className={s.muted}>
        <TextButton onClick={() => openDialog("account")}>Log in</TextButton> to keep these questions for your next visit.
      </p>
    );
  if (!saved.list.length) return null;

  const remove = async (w: SavedWords) => {
    const ok = await confirm({
      title: `Delete ${whose(w.label)} questions?`,
      body: "You can save them again after matching.",
      confirmLabel: "Delete",
      cancelLabel: "Keep",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.accountDeleteWords(w.id);
      saved.removed(w.id);
      toast(`Deleted ${whose(w.label)} questions.`, "success");
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't delete those questions. Try again."), "error");
    }
  };

  return (
    <section className={s.saved} aria-labelledby={titleId}>
      <h3 id={titleId} className={s.label}>
        Saved
      </h3>
      <ul className={s.savedList}>
        {saved.list.map((w) => (
          <li key={w.id} className={s.item}>
            <span className={s.itemText}>
              <strong className={s.itemName}>{wordsTag(w.label)}</strong>
              <span className={s.itemLine}>
                {questionCount(Object.keys(w.words).length)} · saved {savedOn(w.created_at)}
              </span>
            </span>
            <Button
              busy={starting && using === w.id}
              busyLabel="Starting…"
              disabled={starting}
              onClick={() => {
                setUsing(w.id);
                onUse(w);
              }}
            >
              Use
            </Button>
            <button type="button" className={s.remove} aria-label={`Delete ${whose(w.label)} questions`} disabled={starting} onClick={() => remove(w)}>
              ×
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
