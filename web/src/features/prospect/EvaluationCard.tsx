"use client";

import { Badge, Button, Notice, ProgressBar, type Tone } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/features/shell/UiContext";
import type { Evaluation, Outcome } from "@/lib/api/types";
import { Confetti } from "./Confetti";
import { prospectConfig } from "./prospectConfig";
import { useCountUp } from "@/lib/useCountUp";
import { useEvaluation } from "./useEvaluation";
import s from "./EvaluationCard.module.css";

const OUTCOME: Record<Outcome, { label: string; tone: Tone }> = {
  sold: { label: "Sale made", tone: "success" },
  walked: { label: "Buyer walked away", tone: "danger" },
  active: { label: "Incomplete", tone: "neutral" },
  incomplete: { label: "Incomplete", tone: "neutral" },
};

const gradeTone = (g: string): Tone => (g === "A" || g === "B" ? "success" : g === "C" ? "warning" : "danger");

function Bullets({ title, items }: { title: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h4 className={s.listTitle}>{title}</h4>
      <ul className={s.list}>
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

function Result({ ev }: { ev: Evaluation }) {
  const { prospect, startProspect } = useSession();
  const { openDialog, closeDialog } = useUi();
  const score = useCountUp(ev.overall_score || 0);
  const grade = (ev.grade || "?").toUpperCase();
  const outcome = OUTCOME[ev.outcome] ?? OUTCOME.incomplete;
  const celebrate = ev.outcome === "sold" || (prospectConfig.celebrateGrades as readonly string[]).includes(grade);

  const tryAgain = async () => {
    if (!prospect) return;
    closeDialog();
    await startProspect(prospect.difficulty, prospect.productType);
  };

  return (
    <div className={s.card}>
      {celebrate && <Confetti />}
      <div className={s.head}>
        <span className={s.score} aria-label={`Score ${ev.overall_score} percent`}>
          {score}%
        </span>
        <Badge tone={gradeTone(grade)}>Grade {grade}</Badge>
        <Badge tone={outcome.tone}>{outcome.label}</Badge>
      </div>

      <ul className={s.criteria}>
        {Object.entries(ev.criteria_scores ?? {}).map(([name, c]) => (
          <li key={name} className={s.criterion}>
            <span className={s.cName}>{name.replace(/_/g, " ")}</span>
            <ProgressBar value={c.score} label={name.replace(/_/g, " ")} caption={`${c.score}%`} />
            {c.feedback && <p className={s.feedback}>{c.feedback}</p>}
          </li>
        ))}
      </ul>

      <Bullets title="Strengths" items={ev.strengths ?? []} />
      <Bullets title="Areas to improve" items={ev.improvements ?? []} />
      {ev.coach_tip && (
        <p className={s.tip}>
          <strong>Coach tip:</strong> {ev.coach_tip}
        </p>
      )}
      {ev.summary && <p className={s.summary}>{ev.summary}</p>}

      <div className={s.actions}>
        <Button variant="primary" onClick={() => openDialog("review")}>
          Walk it back
        </Button>
        <Button onClick={tryAgain}>Try again</Button>
      </div>
    </div>
  );
}

/** Loading, error or finished evaluation. The one body shared by modal, panel and inline. */
export function EvaluationBody() {
  const { state, run } = useEvaluation();
  if (state.status === "loading") return <Notice kind="loading">Generating evaluation…</Notice>;
  if (state.status === "error")
    return (
      <Notice
        kind="error"
        action={
          <Button variant="ghost" onClick={run}>
            Try again
          </Button>
        }
      >
        {state.error || "The evaluation failed."}
      </Notice>
    );
  return state.result ? <Result ev={state.result} /> : null;
}
