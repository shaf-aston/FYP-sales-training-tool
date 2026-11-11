"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Dialog, Notice } from "@/components/ui";
import { ReviewSummary, ReviewTurns } from "@/features/sell/ReviewTurns";
import { api, errorText } from "@/lib/api/client";
import type { CallReq, ChatMsg, Difficulty, Review } from "@/lib/api/types";

type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; review: Review };

function intro(review: Review, prospect: string): string {
  const n = review.pivotal_turns.length;
  if (n) return `${n} turn${n > 1 ? "s" : ""} cost you ground with ${prospect}. Practise from ${n > 1 ? "any of them" : "it"} below.`;
  if (review.summary.went_well) return `Nothing you said lost ground with ${prospect}. Good call.`;
  return `No single turn cost you ground, but the call did not land. Work on this: ${review.summary.work_on}`;
}

/** The call before `turn` as chat lines, ending with the prospect's (a line they did not answer is left out). */
function linesBefore(review: Review, turn: number): ChatMsg[] {
  return review.turns
    .filter((t) => t.turn < turn && t.buyer)
    .flatMap((t): ChatMsg[] => [
      { role: "user", content: t.seller },
      { role: "assistant", content: t.buyer ?? "" },
    ]);
}

type BodyProps = Pick<Props, "call" | "prospect" | "difficulty" | "practise">;

function CallReviewBody({ call, prospect, difficulty, practise }: BodyProps) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .callsReview(call, difficulty)
      .then((review) => live && setLoad({ status: "ready", review }))
      .catch((err) => live && setLoad({ status: "error", message: errorText(err, "Couldn't review the call.") }));
    return () => {
      live = false;
    };
  }, [call, difficulty, attempt]);

  const retry = useCallback(() => {
    setLoad({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  if (load.status === "loading") return <Notice kind="loading">Going through the call…</Notice>;
  if (load.status === "error")
    return (
      <Notice kind="error" onRetry={retry}>
        {load.message}
      </Notice>
    );

  const { review } = load;
  if (!review.turns.length) return <Notice kind="empty">None of your turns got a reply to review.</Notice>;
  return (
    <>
      <p>{intro(review, prospect)}</p>
      <ReviewSummary review={review} />
      <ReviewTurns
        review={review}
        seller="You"
        buyer={prospect}
        pivotalAction={(t) => {
          // With nothing before it, the main "Practise" button already starts there.
          const replay = linesBefore(review, t.turn);
          return (
            replay.length > 0 && (
              <Button disabled={practise.disabled} onClick={() => practise.start(replay)}>
                Practise from here
              </Button>
            )
          );
        }}
      />
    </>
  );
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** The call exactly as it was read (with the rep), so the review matches the screen. */
  call: CallReq;
  /** Rated at the difficulty the learner picked. */
  difficulty: Difficulty;
  /** The prospect's name as the call shows it (labels their lines). */
  prospect: string;
  /** Practise against this prospect: from the start, or (with `replay`) from inside the real call. */
  practise: { label: string; start: (replay?: ChatMsg[]) => void; disabled?: boolean };
}

/** Turn-by-turn review of a real call: what you said, how they took it, which turns cost ground, and practice from there. */
export function CallReviewDialog({ open, onClose, call, prospect, difficulty, practise }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Your real call"
      size="lg"
      actions={
        <Button variant="primary" disabled={practise.disabled} onClick={() => practise.start()}>
          {practise.label}
        </Button>
      }
    >
      {open && <CallReviewBody call={call} prospect={prospect} difficulty={difficulty} practise={practise} />}
    </Dialog>
  );
}
