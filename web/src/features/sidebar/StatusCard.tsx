"use client";

import { Card, Eyebrow } from "@/components/ui";
import { stageMeta } from "@/lib/labels";
import { useSession, type SellSession } from "@/features/session/SessionContext";
import { readinessBand } from "@/features/sell/options";
import s from "./StatusCard.module.css";

/** Sell mode: who the AI buyer is and how warm they are (the buyer panel has the numbers). */
function buyerLine(b: SellSession | null): string {
  if (!b) return "Not set up yet";
  const name = b.persona.name || "Your buyer";
  if (b.outcome === "sold") return `${name} said yes`;
  if (b.outcome === "walked") return `${name} walked away`;
  if (b.ended) return "Conversation over";
  return `${name} · ${readinessBand(Math.round(b.state.readiness * 100))}`;
}

export function StatusCard() {
  const { mode, stage, sellSession } = useSession();
  const sell = mode === "sell";
  const label = sell ? buyerLine(sellSession) : stageMeta(stage).label;

  return (
    <Card tone="accent" className={s.card} aria-label={sell ? "Your buyer" : "Stage of the sale"}>
      <Eyebrow>{sell ? "Buyer" : "Stage"}</Eyebrow>
      <p key={label} className={s.stageName} aria-live="polite">
        {label}
      </p>
    </Card>
  );
}
