"use client";

import { useId } from "react";
import type { CallReadRes } from "@/lib/api/types";
import { config } from "@/lib/config";
import s from "./SpeakerPicker.module.css";

interface Props {
  call: CallReadRes;
  /** True while the call is read again with another speaker as the learner. */
  busy: boolean;
  /** The speakers were named by AI from a recording, so the learner should check them. */
  aiLabelled?: boolean;
  onPick: (name: string) => void;
}

/** Who is who on the call: the guessed rep is marked "You"; tapping another speaker says "that's me". */
export function SpeakerPicker({ call, busy, aiLabelled, onPick }: Props) {
  const id = useId();
  const { speakers, rep, prospect } = call;
  return (
    <section className={s.picker} aria-labelledby={id}>
      <h3 id={id} className={s.label}>
        Which one is you?
      </h3>
      <div className={s.chips} role="group" aria-labelledby={id}>
        {speakers.map((sp) => {
          const you = sp.name === rep.name;
          return (
            <button
              key={sp.name}
              type="button"
              className={s.chip}
              aria-pressed={you}
              disabled={busy}
              title={`${sp.turns} turns · ${sp.questions} questions`}
              onClick={() => !you && onPick(sp.name)}
            >
              <span className={s.name}>{sp.name}</span>
              {you && <span className={s.you}>You</span>}
              {sp.name === prospect && <span className={s.tag}>Prospect</span>}
            </button>
          );
        })}
      </div>
      <p className={s.how} role="status">
        {busy ? (
          "Reading it again…"
        ) : (
          <>
            How we guessed: {config.calls.repGuess[rep.how].toLowerCase()}.
            {!rep.sure && !aiLabelled && <span className={s.unsure}> Not you? Tap your name.</span>}
          </>
        )}
      </p>
      {aiLabelled && <p className={s.aiNote}>Speakers were labelled by AI from what was said; tap the one that&apos;s you if it&apos;s wrong.</p>}
    </section>
  );
}
