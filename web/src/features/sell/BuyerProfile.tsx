"use client";

import { Badge, Button, Card, ProgressBar, Select, Switch } from "@/components/ui";
import { useSession, type SellSession } from "@/features/session/SessionContext";
import { EvaluationBody } from "./EvaluationCard";
import { difficultyTone, evalDisplayOptions, readinessBand, signed } from "./options";
import { useEvaluation } from "./useEvaluation";
import { useReadinessDelta } from "./useReadinessDelta";
import s from "./BuyerProfile.module.css";

/** How the conversation ended, or null while it is still going. */
function endLine(b: SellSession): string | null {
  if (b.outcome === "sold") return "Said yes";
  if (b.outcome === "walked") return "Walked away";
  return b.ended ? "Conversation over" : null;
}

/** Top of the Buyer tab while selling: who the buyer is, how warm they are, and scoring. */
export function BuyerProfile({ sellSession }: { sellSession: SellSession }) {
  const { sellSettings, setSellSettings } = useSession();
  const { state, run, display, forThisSession } = useEvaluation();
  const pct = Math.round(sellSession.state.readiness * 100);
  const delta = useReadinessDelta(pct);

  const name = sellSession.persona.name || "Alex"; // same unnamed-persona default as the backend
  const turns = sellSession.state.turn_count;
  const ended = endLine(sellSession);
  const evaluating = forThisSession && state.status === "loading";

  return (
    <div className={s.profile}>
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
            {signed(delta.n)}%
          </span>
        )}
      </section>

      <p className={s.turns}>
        Turn <strong>{turns}</strong>
        {ended && <> · {ended}</>}
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
  );
}
