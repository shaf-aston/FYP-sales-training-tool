import type { ReactNode } from "react";
import { Badge } from "@/components/ui";
import type { Review, ReviewTurn } from "@/lib/api/types";
import { signed } from "./options";
import s from "./ReviewTurns.module.css";

function Dots({ rating }: { rating: number }) {
  return (
    <span className={s.rating} role="img" aria-label={`Rated ${rating} out of 5`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} className={i <= rating ? s.dotOn : s.dot} />
      ))}
    </span>
  );
}

/** One spoken line with who said it, e.g. "YOU  Hi, thanks for taking the call." */
export function ReviewLine({ who, children }: { who: string; children: ReactNode }) {
  return (
    <p className={s.said}>
      <span className={s.who}>{who}</span>
      <span>{children}</span>
    </p>
  );
}

interface Props {
  review: Review;
  /** Labels for the two sides, e.g. "You" and "Buyer". */
  seller: string;
  buyer: string;
  /** Turns after this one were replaced (greyed, marked "Replaced"). */
  cutoff?: number;
  /** Extra controls under a pivotal turn that is still current (e.g. "Say this differently"). */
  pivotalAction?: (turn: ReviewTurn) => ReactNode;
  /** Give every current turn the controls, not only pivotal ones: a call with no costly turn still has lines
   *  worth saying better (sell mode's review). A real call's review keeps them to its turning points. */
  actionOnEveryTurn?: boolean;
}

/** One line under the intro: how many turns and the average rating. */
export function ReviewSummary({ review }: { review: Review }) {
  const { turn_count, average_rating } = review.summary;
  return (
    <p className={s.muted}>
      {turn_count} {turn_count === 1 ? "turn" : "turns"} · average {average_rating} out of 5
    </p>
  );
}

/** A sell review turn by turn: what each side said, the rating, why, and which turns cost ground. Read-only. */
export function ReviewTurns({ review, seller, buyer, cutoff = Infinity, pivotalAction, actionOnEveryTurn = false }: Props) {
  const pivotal = new Set(review.pivotal_turns);
  return (
    <ol className={s.turns}>
        {review.turns.map((t) => {
          const gone = t.turn > cutoff;
          const key = pivotal.has(t.turn);
          const change = Math.round(t.readiness_change * 100);
          return (
            <li key={t.turn} className={`${s.turn} ${key ? s.pivotal : ""} ${gone ? s.gone : ""}`}>
              <div className={s.turnHead}>
                <strong>Turn {t.turn}</strong>
                <Dots rating={t.rating} />
                {change !== 0 && <Badge tone={change > 0 ? "success" : "danger"}>{signed(change)}% interest</Badge>}
                {gone && <Badge>Replaced</Badge>}
              </div>
              <ReviewLine who={seller}>{t.seller}</ReviewLine>
              {t.buyer && <ReviewLine who={buyer}>{t.buyer}</ReviewLine>}
              {t.reasons.length ? (
                <ul className={s.reasons}>
                  {t.reasons.map((r, i) => (
                    <li key={i}>{r}</li>
                  ))}
                </ul>
              ) : (
                !t.noticed?.length && <p className={s.muted}>Nothing here moved them either way.</p>
              )}
              {t.noticed?.length ? (
                <ul className={s.noticed}>
                  {t.noticed.map((n) => (
                    <li key={n.label}>{n.reason}</li>
                  ))}
                </ul>
              ) : null}
              {(key || actionOnEveryTurn) && !gone && pivotalAction?.(t)}
            </li>
          );
        })}
    </ol>
  );
}
