"use client";

import { useState } from "react";
import { Button, Markdown, Notice, Select, TextInput } from "@/components/ui";
import { api } from "@/lib/api/client";
import type { TrainingStyle } from "@/lib/api/types";
import { storageKeys } from "@/lib/config";
import { useStoredState } from "@/lib/useStoredState";
import { useSession } from "@/features/session/SessionContext";
import s from "./coach.module.css";

const STYLES: { value: TrainingStyle; label: string }[] = [
  { value: "tactical", label: "Direct coaching style" },
  { value: "socratic", label: "Ask me back" },
  { value: "teacher", label: "Explain it clearly" },
];

const parseStyle = (raw: string): TrainingStyle | undefined => STYLES.find((x) => x.value === raw)?.value;

export function AskCoach() {
  const { sessionId, handleExpired } = useSession();
  const [style, setStyle] = useStoredState<TrainingStyle>(storageKeys.trainingStyle, "tactical", parseStyle);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const ask = async () => {
    const q = question.trim();
    if (!q || !sessionId || busy) return;
    setBusy(true);
    setError("");
    try {
      const res = await api.askCoach(sessionId, q, style);
      setAnswer(res.answer);
    } catch (err) {
      if (!handleExpired(err)) setError(err instanceof Error ? err.message : "The coach could not answer. Try again.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form
      className={s.ask}
      onSubmit={(e) => {
        e.preventDefault();
        void ask();
      }}
    >
      <Select label="Ask the coach" value={style} onChange={(e) => setStyle(e.target.value as TrainingStyle)}>
        {STYLES.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </Select>
      <div className={s.row}>
        <TextInput
          label="Your question"
          hideLabel
          placeholder="e.g. How do I handle the price objection?"
          value={question}
          disabled={busy}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <Button type="submit" variant="primary" busy={busy} busyLabel="Thinking…" disabled={!question.trim()}>
          Ask coach
        </Button>
      </div>
      <div aria-live="polite">
        {error && <Notice kind="error">{error}</Notice>}
        {answer && !error && <Markdown className={s.answer} text={answer} />}
      </div>
    </form>
  );
}
