"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Markdown, Notice, Panel, Segmented, TextArea } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { QuizResult, QuizType } from "@/lib/api/types";
import { config } from "@/lib/config";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { QuizResultCard } from "./QuizResultCard";
import s from "./quiz.module.css";

const TYPES: { value: QuizType; label: string }[] = [
  { value: "stage", label: "Stage" },
  { value: "next_move", label: "Next move" },
  { value: "direction", label: "Direction" },
];

const errText = (e: unknown, fallback: string) => (e instanceof Error && e.message ? e.message : fallback);

export function QuizPanel() {
  const { mode, sessionId, prospect, handleExpired } = useSession();
  const { closeSidePanel } = useUi();
  const isProspect = mode === "prospect";
  const sid = isProspect ? prospect?.sessionId : sessionId;

  const [type, setType] = useState<QuizType>("stage");
  const [question, setQuestion] = useState("");
  const [turn, setTurn] = useState<number | undefined>();
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState("");
  const [answer, setAnswer] = useState("");
  const [empty, setEmpty] = useState(false);
  const [checking, setChecking] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [result, setResult] = useState<QuizResult | null>(null);

  const load = useCallback(async () => {
    if (!sid) return;
    setLoading(true);
    setLoadError("");
    setResult(null);
    setAnswer("");
    setEmpty(false);
    setSubmitError("");
    try {
      const q = isProspect ? await api.prospectQuizQuestion(sid) : await api.quizQuestion(sid, type);
      setQuestion(q.question);
      setTurn(q.turn);
    } catch (err) {
      if (!handleExpired(err)) setLoadError(errText(err, "Could not load a question. Try again."));
    } finally {
      setLoading(false);
    }
  }, [sid, isProspect, type, handleExpired]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch a question when the panel opens or the type changes
    void load();
  }, [load]);

  const submit = async () => {
    const text = answer.trim();
    if (!text) {
      setEmpty(true);
      return;
    }
    if (!sid) return;
    setEmpty(false);
    setSubmitError("");
    setChecking(true);
    try {
      const res = isProspect
        ? await api.prospectQuizAnswer(sid, turn as number, text)
        : await api.quizAnswer(sid, type, text);
      setResult(res);
    } catch (err) {
      if (!handleExpired(err)) setSubmitError(errText(err, "Could not check your answer. Try again."));
    } finally {
      setChecking(false);
    }
  };

  const needsTurn = isProspect && !loading && !loadError && turn === undefined;
  const canAnswer = !loading && !loadError && !needsTurn && !!question;

  return (
    <Panel kicker="Quiz mode" title="Skill check" onClose={closeSidePanel}>
      <div className={s.stack}>
        {!isProspect && <Segmented label="Quiz type" options={TYPES} value={type} onChange={setType} />}
        {loading && <Notice kind="loading">Loading question…</Notice>}
        {loadError && (
          <Notice
            kind="error"
            action={
              <Button variant="secondary" onClick={() => void load()}>
                Try again
              </Button>
            }
          >
            {loadError}
          </Notice>
        )}
        {needsTurn && <Notice kind="empty">Talk to the buyer first, then come back for a question about the conversation.</Notice>}
        {!sid && !loading && <Notice kind="empty">Start a conversation to unlock the quiz.</Notice>}
        {canAnswer && (
          <>
            <Markdown className={s.question} text={question} />
            <TextArea
              label="Your answer"
              rows={4}
              maxLength={config.maxMessageLength}
              count={answer.length}
              value={answer}
              disabled={checking}
              onChange={(e) => {
                setAnswer(e.target.value);
                if (empty) setEmpty(false);
              }}
            />
            {empty && (
              <Notice kind="error">Please enter an answer.</Notice>
            )}
            {submitError && <Notice kind="error">{submitError}</Notice>}
            {!result && (
              <Button variant="primary" busy={checking} busyLabel="Checking…" onClick={() => void submit()}>
                Submit
              </Button>
            )}
            {result && (
              <>
                <QuizResultCard result={result} kind={isProspect ? "prospect" : type} />
                <Button variant="secondary" onClick={() => void load()}>
                  Next question
                </Button>
              </>
            )}
          </>
        )}
      </div>
    </Panel>
  );
}
