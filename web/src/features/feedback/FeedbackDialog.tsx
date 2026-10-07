"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Button, Dialog, Notice, TextArea } from "@/components/ui";
import { api } from "@/lib/api/client";
import { config } from "@/lib/config";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import s from "./FeedbackDialog.module.css";

const STARS = [1, 2, 3, 4, 5];
const THANKS_MS = 1_500;

function StarRating({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  const [hover, setHover] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  const move = (e: KeyboardEvent, n: number) => {
    const step = e.key === "ArrowRight" || e.key === "ArrowUp" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowDown" ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = Math.min(STARS.length, Math.max(1, n + step));
    onChange(next);
    refs.current[next - 1]?.focus();
  };

  return (
    <div role="radiogroup" aria-label="Rating" className={s.stars} onMouseLeave={() => setHover(0)}>
      {STARS.map((n) => (
        <button
          key={n}
          ref={(el) => {
            refs.current[n - 1] = el;
          }}
          type="button"
          role="radio"
          aria-checked={value === n}
          aria-label={`${n} star${n > 1 ? "s" : ""}`}
          tabIndex={value === n || (!value && n === 1) ? 0 : -1}
          className={`${s.star} ${n <= (hover || value) ? s.on : ""} ${n === value ? s.picked : ""}`}
          onClick={() => onChange(n)}
          onMouseEnter={() => setHover(n)}
          onKeyDown={(e) => move(e, n)}
        >
          ★
        </button>
      ))}
    </div>
  );
}

export function FeedbackDialog() {
  const { dialog, closeDialog } = useUi();
  const { mode } = useSession();
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [hint, setHint] = useState(false);
  const [error, setError] = useState("");
  const [sent, setSent] = useState(false);

  // After a send, show thanks briefly, then close and reset the form.
  useEffect(() => {
    if (!sent) return;
    const t = setTimeout(() => {
      closeDialog();
      setSent(false);
      setRating(0);
      setComment("");
    }, THANKS_MS);
    return () => clearTimeout(t);
  }, [sent, closeDialog]);

  const submit = async () => {
    const text = comment.trim();
    if (!rating && !text) {
      setHint(true);
      return;
    }
    setHint(false);
    setError("");
    setBusy(true);
    try {
      await api.feedback({ rating: rating || null, comment: text || null, page: mode === "sell" ? "prospect" : "chat" });
      setSent(true);
    } catch {
      setError("Your feedback did not send. Check your connection and try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={dialog === "feedback"}
      onClose={closeDialog}
      size="sm"
      title="Quick feedback"
      actions={
        !sent && (
          <Button variant="primary" busy={busy} busyLabel="Sending…" onClick={submit}>
            Send feedback
          </Button>
        )
      }
    >
      {sent ? (
        <div className={s.thanks} role="status">
          <svg className={s.check} viewBox="0 0 52 52" aria-hidden="true">
            <circle cx="26" cy="26" r="24" />
            <path d="M15 27l8 8 14-16" />
          </svg>
          <p>Thanks for your feedback!</p>
        </div>
      ) : (
        <div className={s.form}>
          <StarRating
            value={rating}
            onChange={(n) => {
              setRating(n);
              setHint(false);
            }}
          />
          <TextArea
            label="Comment"
            hideLabel
            rows={4}
            maxLength={config.maxFeedbackLength}
            count={comment.length}
            placeholder="What worked well? What should feel easier?"
            value={comment}
            onChange={(e) => {
              setComment(e.target.value);
              setHint(false);
            }}
          />
          {hint && <Notice kind="empty">Pick a star rating or write a short comment first.</Notice>}
          {error && <Notice kind="error">{error}</Notice>}
        </div>
      )}
    </Dialog>
  );
}
