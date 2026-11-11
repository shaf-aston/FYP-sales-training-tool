"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Dialog, Notice } from "@/components/ui";
import { ReviewSummary, ReviewTurns } from "@/features/sell/ReviewTurns";
import { api, errorText } from "@/lib/api/client";
import type { CallReq, Review } from "@/lib/api/types";

type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; review: Review };

function intro(review: Review, prospect: string): string {
  const n = review.pivotal_turns.length;
  if (n) return `${n} turn${n > 1 ? "s" : ""} cost you ground with ${prospect}. ${n > 1 ? "They're" : "It's"} marked below.`;
  if (review.summary.went_well) return `Nothing you said lost ground with ${prospect}. Good call.`;
  return `No single turn cost you ground, but the call did not land. Work on this: ${review.summary.work_on}`;
}

function CallReviewBody({ call, prospect }: { call: CallReq; prospect: string }) {
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .callsReview(call)
      .then((review) => live && setLoad({ status: "ready", review }))
      .catch((err) => live && setLoad({ status: "error", message: errorText(err, "Couldn't review the call.") }));
    return () => {
      live = false;
    };
  }, [call, attempt]);

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
      <ReviewTurns review={review} seller="You" buyer={prospect} />
    </>
  );
}

interface Props {
  open: boolean;
  onClose: () => void;
  /** The call exactly as it was read (with the rep), so the review matches the screen. */
  call: CallReq;
  /** The prospect's name as the call shows it (labels their lines). */
  prospect: string;
  /** Primary action under the review, e.g. practise against this prospect. */
  practise: { label: string; onClick: () => void };
}

/** Read-only turn-by-turn review of a real call: what you said, how they took it, which turns cost ground. */
export function CallReviewDialog({ open, onClose, call, prospect, practise }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Your real call"
      size="lg"
      actions={
        <Button variant="primary" onClick={practise.onClick}>
          {practise.label}
        </Button>
      }
    >
      {open && <CallReviewBody call={call} prospect={prospect} />}
    </Dialog>
  );
}
