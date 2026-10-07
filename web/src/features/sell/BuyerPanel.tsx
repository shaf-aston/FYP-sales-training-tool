"use client";

import { useState } from "react";
import { Badge, Button, Card, Panel, ProgressBar, Select, Switch } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { EvaluationBody } from "./EvaluationCard";
import { difficultyTone, evalDisplayOptions, readinessBand } from "./options";
import { useEvaluation } from "./useEvaluation";
import { useReadinessDelta } from "./useReadinessDelta";
import s from "./BuyerPanel.module.css";

/** Right-hand column while selling to the AI buyer: who they are, how warm they are, and settings. */
export function BuyerPanel() {
  const { sellSession, sellSettings, setSellSettings } = useSession();
  const { state, run, display, forThisSession } = useEvaluation();
  // Open by default: knowing who you are selling to is the point of the panel.
  const [open, setOpen] = useState(true);
  const pct = Math.round((sellSession?.state.readiness ?? 0) * 100);
  const delta = useReadinessDelta(pct);

  if (!sellSession) return null;
  const name = sellSession.persona.name || "Alex";
  const turns = sellSession.state.turn_count;
  const evaluating = forThisSession && state.status === "loading";

  return (
    <Panel title="Buyer profile" hideHeadOnPhone>
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
            <Badge tone={difficultyTone[sellSession.difficulty]}>{sellSession.difficulty}</Badge>
          </div>
          <p className={s.background}>{sellSession.persona.background}</p>
          {sellSession.persona.personality && <p className={s.background}>{sellSession.persona.personality}</p>}
          {sellSession.pick.objection && (
            <p className={s.background}>
              <strong>Practising:</strong> “{sellSession.pick.objection}”
            </p>
          )}
        </section>

        <section className={s.readiness}>
          <ProgressBar value={pct} label="Buying readiness" caption={`${pct}% · ${readinessBand(pct)}`} />
          {delta && (
            <span key={delta.key} className={`${s.delta} ${delta.n > 0 ? s.up : s.down}`} aria-hidden="true">
              {delta.n > 0 ? "+" : ""}
              {delta.n}%
            </span>
          )}
        </section>

        <p className={s.turns}>
          Turn <strong>{sellSession.maxTurns ? `${turns} / ${sellSession.maxTurns}` : turns}</strong>
        </p>

        {sellSettings.showHints && (
          <Card tone="accent" aria-live="polite">
            <p className={s.hint}>{sellSession.hint || "A hint shows after the buyer's next reply."}</p>
          </Card>
        )}

        <Button variant="danger" block busy={evaluating} busyLabel="Scoring…" disabled={turns < 1} onClick={run}>
          End and score
        </Button>

        {display === "panel" && forThisSession && state.status !== "idle" && <EvaluationBody />}

        <details className={s.settings}>
          <summary>Hints and score</summary>
          <div className={s.settingsBody}>
            <Switch
              label="Show hints"
              checked={sellSettings.showHints}
              onChange={(showHints) => setSellSettings({ ...sellSettings, showHints })}
            />
            <Select
              label="Evaluation display"
              value={sellSettings.evalDisplay}
              onChange={(e) => setSellSettings({ ...sellSettings, evalDisplay: e.target.value as typeof display })}
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
