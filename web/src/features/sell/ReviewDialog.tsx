"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Dialog, Notice, TextArea } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { api, errorText } from "@/lib/api/client";
import type { RedoRes, Review, ReviewTurn } from "@/lib/api/types";
import { config } from "@/lib/config";
import { evalStore, gradeOf, useEvalState } from "./evalStore";
import { gradeTone } from "./options";
import { ReviewLine, ReviewSummary, ReviewTurns } from "./ReviewTurns";
import s from "./ReviewDialog.module.css";

type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; review: Review };

function intro(review: Review, grade: string): string {
  const n = review.pivotal_turns.length;
  if (n) return `${n} turn${n > 1 ? "s" : ""} cost you ground. Try ${n > 1 ? "them" : "it"} again below and see what they say.`;
  if (review.summary.went_well && gradeTone(grade) !== "danger") return "Nothing here lost you ground. Good session.";
  return `No single turn cost you ground, but the session did not land. Work on this: ${review.summary.work_on ?? ""}`;
}

interface RedoProps {
  turn: ReviewTurn;
  laterTurns: number;
  done: RedoRes | undefined;
  onDone: (res: RedoRes) => void;
}

function Redo({ turn, laterTurns, done, onDone }: RedoProps) {
  const { sellSession, handleExpired } = useSession();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    if (!sellSession || !draft.trim()) return;
    setWaiting(true);
    setError("");
    try {
      const res = await api.sellRedo(sellSession.sessionId, turn.turn, draft.trim());
      setSent(draft.trim());
      onDone(res);
      setEditing(false);
    } catch (err) {
      if (handleExpired(err)) return;
      setError(errorText(err, "That didn't go through."));
    } finally {
      setWaiting(false);
    }
  };

  if (done)
    return (
      <div className={s.redoResult}>
        <ReviewLine who="You">{sent}</ReviewLine>
        <ReviewLine who="Buyer">{done.message}</ReviewLine>
        <p className={s.muted}>The chat now continues from here: close this to carry on with the buyer.</p>
      </div>
    );

  if (!editing)
    return (
      <Button variant="ghost" onClick={() => setEditing(true)}>
        Say this differently
      </Button>
    );

  return (
    <div className={s.redo}>
      <p className={s.warn}>
        Saying this differently replaces the {laterTurns} turn{laterTurns === 1 ? "" : "s"} that came after it. The buyer will reply for real from here.
      </p>
      <TextArea label="What would you say instead?" rows={3} maxLength={config.maxMessageLength} count={draft.length} value={draft} onChange={(e) => setDraft(e.target.value)} disabled={waiting} />
      <div aria-live="polite">{waiting && <Notice kind="loading">Seeing how they respond…</Notice>}</div>
      {error && (
        <Notice kind="error">
          {error} Your text is kept - try again.
        </Notice>
      )}
      <div className={s.row}>
        <Button variant="primary" busy={waiting} busyLabel="Trying…" onClick={submit} disabled={!draft.trim()}>
          Try it
        </Button>
        <Button variant="ghost" onClick={() => setEditing(false)} disabled={waiting}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

function ReviewBody() {
  const { sellSession, handleExpired, refreshSell } = useSession();
  const evalState = useEvalState();
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [redone, setRedone] = useState<Record<number, RedoRes>>({});

  const sid = sellSession?.sessionId;
  useEffect(() => {
    if (!sid) return;
    let live = true;
    api
      .sellReview(sid)
      .then((review) => live && setLoad({ status: "ready", review }))
      .catch((err) => {
        if (!live || handleExpired(err)) return;
        setLoad({ status: "error", message: errorText(err, "") });
      });
    return () => {
      live = false;
    };
  }, [sid, attempt, handleExpired]);

  const retry = useCallback(() => {
    setLoad({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  if (!sid) return <Notice kind="empty">There are no turns to review yet.</Notice>;
  if (load.status === "loading") return <Notice kind="loading">Opening the review…</Notice>;
  if (load.status === "error")
    return (
      <Notice kind="error" onRetry={retry}>
        Couldn&apos;t open the review. {load.message}
      </Notice>
    );

  const { review } = load;
  if (!review.turns.length) return <Notice kind="empty">There are no turns to review yet.</Notice>;

  const redoneTurns = Object.keys(redone).map(Number);
  const cutoff = redoneTurns.length ? Math.min(...redoneTurns) : Infinity;

  return (
    <div className={s.body}>
      <p>{intro(review, gradeOf(evalState))}</p>
      <ReviewSummary review={review} />
      <ReviewTurns
        review={review}
        seller="You"
        buyer="Buyer"
        cutoff={cutoff}
        actionOnEveryTurn
        pivotalAction={(t) => (
          <Redo
            turn={t}
            laterTurns={review.turns.length - t.turn}
            done={redone[t.turn]}
            onDone={(res) => {
              setRedone((r) => ({ ...r, [t.turn]: res }));
              // The chat shows the conversation as the buyer now remembers it, then the old score (for the call
              // before this redo) goes: in that order, or the still-ended call is scored, and so ended, again.
              void refreshSell().then(() => evalStore.reset());
            }}
          />
        )}
      />
    </div>
  );
}

export function ReviewDialog() {
  const { dialog, closeDialog } = useUi();
  const open = dialog === "review";
  return (
    <Dialog open={open} onClose={closeDialog} title="Walk it back" size="lg">
      {open && <ReviewBody />}
    </Dialog>
  );
}
