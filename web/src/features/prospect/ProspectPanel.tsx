"use client";

import { useState } from "react";
import { Badge, Button, Card, Eyebrow, Panel, ProgressBar, Select, Switch } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { config } from "@/lib/config";
import { EvaluationBody } from "./EvaluationCard";
import { difficultyTone, evalDisplayOptions } from "./prospectConfig";
import { useEvaluation } from "./useEvaluation";
import { useReadinessDelta } from "./useReadinessDelta";
import s from "./ProspectPanel.module.css";

const band = (pct: number) =>
  pct < config.readinessBands.low ? "At risk" : pct < config.readinessBands.mid ? "Warming up" : "Ready";

/** Right-hand column while practising with a buyer: who they are, how warm they are, and settings. */
export function ProspectPanel() {
  const { prospect, prospectSettings, setProspectSettings } = useSession();
  const { state, run, display, forThisSession } = useEvaluation();
  const [open, setOpen] = useState(false);
  const pct = Math.round((prospect?.state.readiness ?? 0) * 100);
  const delta = useReadinessDelta(pct);

  if (!prospect) return null;
  const name = prospect.persona.name || "Alex";
  const turns = prospect.state.turn_count;
  const evaluating = forThisSession && state.status === "loading";

  return (
    <Panel kicker="Prospect practice" title="Buyer profile">
      <button type="button" className={s.bar} aria-expanded={open} aria-controls="buyer-details" onClick={() => setOpen((o) => !o)}>
        <span>
          Buyer: {name} · {pct}% ready
        </span>
        <span aria-hidden="true" className={open ? s.caretOpen : s.caret}>
          ▾
        </span>
      </button>

      <div id="buyer-details" className={`${s.details} ${open ? s.open : ""}`}>
        <section className={s.persona}>
          <div className={s.nameRow}>
            <h3 className={s.name}>{name}</h3>
            <Badge tone={difficultyTone[prospect.difficulty]}>{prospect.difficulty}</Badge>
          </div>
          <p className={s.background}>{prospect.persona.background}</p>
        </section>

        <section className={s.readiness}>
          <Eyebrow>Buying readiness</Eyebrow>
          <ProgressBar value={pct} label="Buying readiness" caption={`${pct}% · ${band(pct)}`} />
          {delta && (
            <span key={delta.key} className={`${s.delta} ${delta.n > 0 ? s.up : s.down}`} aria-hidden="true">
              {delta.n > 0 ? "+" : ""}
              {delta.n}%
            </span>
          )}
        </section>

        <p className={s.turns}>
          Turn <strong>{prospect.maxTurns ? `${turns} / ${prospect.maxTurns}` : turns}</strong>
        </p>

        {prospectSettings.showHints && (
          <Card tone="accent" aria-live="polite">
            <Eyebrow>Coaching hint</Eyebrow>
            <p className={s.hint}>{prospect.hint || "Hints will appear after the next prospect reply."}</p>
          </Card>
        )}

        <Button variant="danger" block busy={evaluating} busyLabel="Scoring…" disabled={turns < 1} onClick={run}>
          End and score
        </Button>

        {display === "panel" && forThisSession && state.status !== "idle" && <EvaluationBody />}

        <details className={s.settings}>
          <summary>Practice settings</summary>
          <div className={s.settingsBody}>
            <Switch
              label="Show hints"
              checked={prospectSettings.showHints}
              onChange={(showHints) => setProspectSettings({ ...prospectSettings, showHints })}
            />
            <Select
              label="Evaluation display"
              value={prospectSettings.evalDisplay}
              onChange={(e) => setProspectSettings({ ...prospectSettings, evalDisplay: e.target.value as typeof display })}
            >
              {evalDisplayOptions.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </Select>
          </div>
        </details>
      </div>
    </Panel>
  );
}
