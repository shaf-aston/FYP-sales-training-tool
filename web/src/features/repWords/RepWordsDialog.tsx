"use client";

// Buy mode's Rep's words: the rep asks the script's questions in a top rep's words (from a real call) or the team
// SOP's. The script still runs the call; only the wording of the questions that ask the same thing changes.

import { useState } from "react";
import { Button, Dialog, Icon, Notice, Segmented, TextButton } from "@/components/ui";
import { CallSource } from "@/features/calls/CallSource";
import { SpeakerPicker } from "@/features/calls/SpeakerPicker";
import { useCallReader } from "@/features/calls/useCallReader";
import { SopSource } from "@/features/sop/SopSource";
import { useSopReader } from "@/features/sop/useSopReader";
import { useSession } from "@/features/session/SessionContext";
import { api } from "@/lib/api/client";
import { stageMeta } from "@/lib/labels";
import { useUi } from "@/state/UiContext";
import type { WordsChoice } from "@/lib/api/types";
import { SavedWordsList, SaveWords, TeamWords, UseForTeam, useSavedWords, type SavedWordsState } from "./KeepWords";
import { useRepWords, type RepWordsState } from "./useRepWords";
import { questionCount, whose } from "./words";
import s from "./RepWords.module.css";

type Source = "call" | "sop";

// "Try a sample": a top rep's call and an SOP written for what the rep sells, so they match the script.
const callSample = () => api.buyWordsSample("call");
const sopSample = () => api.buyWordsSample("sop");

export function RepWordsDialog() {
  const { dialog, closeDialog } = useUi();
  return (
    <Dialog open={dialog === "repWords"} onClose={closeDialog} title="Rep's words" size="lg">
      {dialog === "repWords" && <RepWordsBody onDone={closeDialog} />}
    </Dialog>
  );
}

function RepWordsBody({ onDone }: { onDone: () => void }) {
  const { repWords, chooseRepWords } = useSession();
  const state = useRepWords();
  const saved = useSavedWords();
  const [source, setSource] = useState<Source>("call");
  const [starting, setStarting] = useState(false);

  const start = async (words: WordsChoice | null) => {
    setStarting(true);
    await chooseRepWords(words);
    setStarting(false);
    onDone();
  };

  if (state.matched) return <Matches state={state} saved={saved} starting={starting} onStart={start} />;
  return (
    <div className={s.body}>
      <p className={s.lede}>
        Hear the call with a top rep&apos;s questions, or your SOP&apos;s. The rep still follows its script; each question that
        asks the same thing is said in their words.
      </p>
      {repWords && (
        <div className={s.active} role="status">
          <Icon name="check" size={16} />
          <span>
            {repWords.team
              ? `This call uses your team's words: ${whose(repWords.label)}, for ${count(Object.keys(repWords.words).length)}.`
              : `This call uses ${whose(repWords.label)} words for ${count(Object.keys(repWords.words).length)}.`}
          </span>
          <TextButton disabled={starting} onClick={() => start(null)}>
            Use the script&apos;s words
          </TextButton>
          <div className={s.keep}>
            <SaveWords choice={repWords} saved={saved} />
            <UseForTeam choice={repWords} />
          </div>
        </div>
      )}
      <TeamWords starting={starting} onUse={start} />
      <SavedWordsList saved={saved} starting={starting} onUse={start} />

      <Segmented<Source>
        label="Take the questions from"
        options={[
          { value: "call", label: "A real call" },
          { value: "sop", label: "Your SOP" },
        ]}
        value={source}
        onChange={setSource}
      />
      {source === "call" ? <FromCall state={state} /> : <FromSop state={state} />}
    </div>
  );
}

const count = questionCount;

/** A real call: read it, check who the rep is, then match their questions. */
function FromCall({ state }: { state: RepWordsState }) {
  const { buyProduct } = useSession();
  const reader = useCallReader(callSample);
  const result = reader.result;
  if (!result) return <CallSource reader={reader} privacy="Read on our server and never stored; the questions you pick stay in this tab unless you save them." />;
  const rep = result.call.rep.name;
  return (
    <div className={s.stack}>
      <SpeakerPicker call={result.call} busy={reader.busy === "read"} aiLabelled={reader.aiLabelled} onPick={reader.pickRep} pick="rep" />
      {state.error && <Notice kind="error">{state.error}</Notice>}
      <Button
        variant="primary"
        block
        busy={state.busy === "match"}
        busyLabel="Matching…"
        disabled={!!reader.busy}
        onClick={() => state.match({ product_type: buyProduct, call: result.source }, rep)}
      >
        Match {rep}&apos;s questions
      </Button>
      <Button variant="ghost" onClick={reader.back}>
        Use another call
      </Button>
    </div>
  );
}

/** An SOP: read it, then match the questions it gives the rep to ask. */
function FromSop({ state }: { state: RepWordsState }) {
  const { buyProduct } = useSession();
  const reader = useSopReader(sopSample);
  const result = reader.result;
  if (!result) return <SopSource reader={reader} />;
  const steps = result.stages.reduce((n, st) => n + st.steps.length, 0);
  return (
    <div className={s.stack}>
      <p className={s.muted}>
        {reader.source}: {result.stages.length} stage{result.stages.length === 1 ? "" : "s"}, {steps} step{steps === 1 ? "" : "s"}.
      </p>
      {state.error && <Notice kind="error">{state.error}</Notice>}
      <Button
        variant="primary"
        block
        busy={state.busy === "match"}
        busyLabel="Matching…"
        onClick={() => state.match({ product_type: buyProduct, stages: result.stages }, "your SOP")}
      >
        Match the SOP&apos;s questions
      </Button>
      <Button variant="ghost" onClick={reader.back}>
        Use another SOP
      </Button>
    </div>
  );
}

/** The script questions the source asks too, each kept or not, then a call in those words. */
function Matches({
  state,
  saved,
  starting,
  onStart,
}: {
  state: RepWordsState;
  saved: SavedWordsState;
  starting: boolean;
  onStart: (w: WordsChoice) => void;
}) {
  const { res, label } = state.matched!;
  const choice: WordsChoice = { product: res.product_type, label, ...state.kept() };
  const n = Object.keys(choice.words).length;
  const sop = label === "your SOP";
  return (
    <div className={s.body}>
      <p className={s.lede}>
        {res.matches.length
          ? `${sop ? "Your SOP" : label} asks ${res.matches.length} of the script's ${res.steps} questions, in ${sop ? "its" : "their"} own words.`
          : `None of the ${count(res.questions)} found asks what the script asks.`}
      </p>
      {res.matches.length ? (
        <ul className={s.matches}>
          {res.matches.map((m) => {
            const on = !state.off.has(m.step);
            return (
              <li key={m.step}>
                <button type="button" className={s.match} aria-pressed={on} onClick={() => state.toggle(m.step)}>
                  <span className={s.tick} aria-hidden="true">
                    {on && <Icon name="check" size={14} />}
                  </span>
                  <span className={s.lines}>
                    <span className={s.theirs}>{m.theirs}</span>
                    {m.probe && <span className={s.probe}>Asked again: {m.probe}</span>}
                    <span className={s.script}>
                      <span className={s.stage}>{m.name || stageMeta(m.stage).label}</span> Script: {m.script}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      ) : (
        <Notice kind="empty">
          Questions match when they ask the same thing as one of the script&apos;s, like &quot;How long has this been on your
          mind?&quot;. Try a longer call, or an SOP that writes out the questions to ask.
        </Notice>
      )}
      <div className={s.actions}>
        {res.matches.length > 0 && (
          <Button
            variant="primary"
            busy={starting}
            busyLabel="Starting…"
            disabled={!n}
            onClick={() => onStart(choice)}
          >
            Start a call with {count(n)} in {whose(label)} words
          </Button>
        )}
        {n > 0 && <SaveWords choice={choice} saved={saved} />}
        {n > 0 && <UseForTeam choice={choice} />}
        <Button variant="ghost" disabled={starting} onClick={state.back}>
          Back
        </Button>
      </div>
    </div>
  );
}
