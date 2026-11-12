"use client";

import { useId } from "react";
import type { CallReadRes } from "@/lib/api/types";
import { config } from "@/lib/config";
import type { AiLabels } from "./useCallReader";
import s from "./SpeakerPicker.module.css";

interface Props {
  call: CallReadRes;
  /** True while the call is read again with another speaker as the learner. */
  busy: boolean;
  /** The speakers were named by AI from a recording, so the learner should check them. */
  aiLabelled?: AiLabels;
  onPick: (name: string) => void;
  /** Who is picked: the learner ("you", their own call) or the rep whose words are borrowed ("rep"). */
  pick?: "you" | "rep";
}

const COPY = {
  you: { question: "Which one is you?", tag: "You", wrong: "Not you? Tap your name.", ai: "tap the one that's you if it's wrong" },
  rep: { question: "Which one is the rep?", tag: "Rep", wrong: "Not the rep? Tap their name.", ai: "tap the rep if it's wrong" },
};

/** Who is who on the call: the guessed rep is marked "You"; tapping another speaker says "that's me". */
export function SpeakerPicker({ call, busy, aiLabelled, onPick, pick = "you" }: Props) {
  const id = useId();
  const copy = COPY[pick];
  const { speakers, rep, prospect } = call;
  return (
    <section className={s.picker} aria-labelledby={id}>
      <h3 id={id} className={s.label}>
        {copy.question}
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
              {you && <span className={s.you}>{copy.tag}</span>}
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
            {!rep.sure && !aiLabelled && <span className={s.unsure}> {copy.wrong}</span>}
          </>
        )}
      </p>
      {aiLabelled === "sure" && (
        <p className={s.aiNote}>Speakers were labelled by AI from what was said; {copy.ai}.</p>
      )}
      {aiLabelled === "unsure" && (
        <p className={s.aiNote}>
          AI couldn&apos;t tell the speakers apart well. Choose &quot;Use another call&quot;, fix the Speaker A / B labels in the
          transcript, then read it again.
        </p>
      )}
    </section>
  );
}
