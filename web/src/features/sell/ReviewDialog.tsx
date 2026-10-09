"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Dialog, Notice, TextArea } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { api, errorText } from "@/lib/api/client";
import type { RedoRes, Review, ReviewTurn } from "@/lib/api/types";
import { config } from "@/lib/config";
import { gradeOf, useEvalState } from "./evalStore";
import { gradeTone, signed } from "./options";
import s from "./ReviewDialog.module.css";

type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; review: Review };

function Dots({ rating }: { rating: number }) {
  return (
    <span className={s.rating} role="img" aria-label={`Rated ${rating} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= rating ? s.dotOn : s.dot} />
      ))}
    </span>
  );
}

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
        <p className={s.said}>
          <span className={s.who}>You</span>
          {sent}
        </p>
        <p className={s.said}>
          <span className={s.who}>Buyer</span>
          {done.message}
        </p>
        <p className={s.muted}>The conversation now continues from here.</p>
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
  const { sellSession, handleExpired } = useSession();
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

  const pivotal = new Set(review.pivotal_turns);
  const redoneTurns = Object.keys(redone).map(Number);
  const cutoff = redoneTurns.length ? Math.min(...redoneTurns) : Infinity;

  return (
    <div className={s.body}>
      <p>{intro(review, gradeOf(evalState))}</p>
      <p className={s.muted}>
        {review.summary.turn_count} {review.summary.turn_count === 1 ? "turn" : "turns"} · average {review.summary.average_rating} out of 5
      </p>
      {redoneTurns.length > 0 && (
        <Card tone="warning" role="status">
          <p>
            The main chat still shows the original conversation, which no longer matches the buyer&apos;s memory. Restarting from here is not
            supported, so start a new buyer to keep going.
          </p>
        </Card>
      )}
      <ol className={s.turns}>
        {review.turns.map((t) => {
          const gone = t.turn > cutoff;
          const change = Math.round(t.readiness_change * 100);
          return (
            <li key={t.turn} className={`${s.turn} ${pivotal.has(t.turn) ? s.pivotal : ""} ${gone ? s.gone : ""}`}>
              <div className={s.turnHead}>
                <strong>Turn {t.turn}</strong>
                <Dots rating={t.rating} />
                {change !== 0 && (
                  <Badge tone={change > 0 ? "success" : "danger"}>
                    {signed(change)}% interest
                  </Badge>
                )}
                {gone && <Badge>Replaced</Badge>}
              </div>
              <p className={s.said}>
                <span className={s.who}>You</span>
                {t.seller}
              </p>
              {t.buyer && (
                <p className={s.said}>
                  <span className={s.who}>Buyer</span>
                  {t.buyer}
                </p>
              )}
              {t.reasons.length ? (
                <ul className={s.reasons}>
                  {t.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              ) : (
                <p className={s.muted}>Nothing here moved them either way.</p>
              )}
              {pivotal.has(t.turn) && !gone && (
                <Redo
                  turn={t}
                  laterTurns={review.turns.length - t.turn}
                  done={redone[t.turn]}
                  onDone={(res) => setRedone((r) => ({ ...r, [t.turn]: res }))}
                />
              )}
            </li>
          );
        })}
      </ol>
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
