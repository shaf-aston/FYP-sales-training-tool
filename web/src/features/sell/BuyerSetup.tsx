"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Icon, Notice, Segmented, Select, TextArea, useConfirm } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { api, errorText } from "@/lib/api/client";
import type { Difficulty, Persona, ProductGroups } from "@/lib/api/types";
import { config } from "@/lib/config";
import { difficultyOptions } from "./options";
import s from "./BuyerSetup.module.css";

/** The general product; must match the backend default product_type (backend/routes/sell.py). */
const GENERAL = "default";
/** Select value meaning "let the server pick the buyer". */
const SURPRISE = "";
/** Objection select values: the buyer picks, or the learner writes one. */
const BUYER_CHOOSES = "";
const OWN = "__own__";

type Groups = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; groups: ProductGroups };

/** The product list rarely changes; keep it so the "New buyer" form opens fully drawn. */
let loadedGroups: ProductGroups | null = null;

interface Props {
  /** Runs after a buyer starts (the Buyer tab folds the form away). */
  onStarted?: () => void;
  /** Shown with a live buyer: close the form without changing anything. */
  onCancel?: () => void;
}

/** Sell mode: set up the AI buyer (product, difficulty, who they are, an objection to practise). */
export function BuyerSetup({ onStarted, onCancel }: Props) {
  const { sellSession, startBuyer, endBuyer } = useSession();
  const confirm = useConfirm();
  const [groups, setGroups] = useState<Groups>(() => (loadedGroups ? { status: "ready", groups: loadedGroups } : { status: "loading" }));
  const [attempt, setAttempt] = useState(0);
  // A new buyer starts from the current product; the first one from general practice.
  const [product, setProduct] = useState(sellSession?.productType ?? GENERAL);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState(SURPRISE);
  const [objectionPick, setObjectionPick] = useState(BUYER_CHOOSES);
  const [ownObjection, setOwnObjection] = useState("");
  const [busy, setBusy] = useState(false);

  const objection = objectionPick === OWN ? ownObjection.trim() : objectionPick;

  useEffect(() => {
    if (loadedGroups) return;
    let live = true;
    api
      .sellProductGroups()
      .then((r) => {
        loadedGroups = r.groups;
        if (live) setGroups({ status: "ready", groups: r.groups });
      })
      .catch((e) => live && setGroups({ status: "error", message: errorText(e, "Couldn't load the product list.") }));
    return () => {
      live = false;
    };
  }, [attempt]);

  // Each product has its own buyers; reload them and clear a pick that no longer exists.
  useEffect(() => {
    let live = true;
    api
      .sellPersonas(product)
      .then((r) => {
        if (!live) return;
        setPersonas(r.personas);
        setPersona((p) => (r.personas.some((x) => x.name === p) ? p : SURPRISE));
      })
      .catch(() => live && setPersonas([]));
    return () => {
      live = false;
    };
  }, [product]);

  const retry = useCallback(() => {
    setGroups({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const shown = sellSession?.difficulty ?? difficulty;
  const picked = personas.find((p) => p.name === persona);

  const start = async (d: Difficulty) => {
    setBusy(true);
    const ok = await startBuyer(d, product, { persona: persona || undefined, objection: objection || undefined });
    setBusy(false);
    if (ok) onStarted?.();
  };

  const roll = () => {
    const others = personas.filter((p) => p.name !== persona);
    const pool = others.length ? others : personas;
    if (pool.length) setPersona(pool[Math.floor(Math.random() * pool.length)].name);
  };

  const changeDifficulty = async (d: Difficulty) => {
    if (d === shown) return;
    if (!sellSession) return setDifficulty(d);
    const ok = await confirm({
      title: "Change difficulty?",
      body: "This ends the current conversation and starts a new one at the new difficulty.",
      confirmLabel: "Reset and change",
    });
    if (!ok) return;
    setDifficulty(d);
    await start(d);
  };

  if (groups.status === "loading") return <Notice kind="loading">Loading products…</Notice>;
  if (groups.status === "error")
    return (
      <Notice kind="error" onRetry={retry}>
        {groups.message}
      </Notice>
    );

  return (
    <div className={s.stack}>
      <Select label="Product" value={product} onChange={(e) => setProduct(e.target.value)}>
        <option value={GENERAL}>General practice</option>
        {(["transactional", "consultative"] as const).map((kind) => (
          <optgroup key={kind} label={kind === "transactional" ? "Transactional" : "Consultative"}>
            {groups.groups[kind].map((p) => (
              <option key={p.id} value={p.id}>
                {p.label}
              </option>
            ))}
          </optgroup>
        ))}
      </Select>

      <Segmented label="Difficulty" options={[...difficultyOptions]} value={shown} onChange={changeDifficulty} />

      <div className={s.field}>
        <div className={s.personaRow}>
          <Select label="Buyer" value={persona} onChange={(e) => setPersona(e.target.value)}>
            <option value={SURPRISE}>Surprise me</option>
            {personas.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
              </option>
            ))}
          </Select>
          <Button onClick={roll} disabled={!personas.length} aria-label="Pick a random buyer" title="Pick a random buyer">
            <Icon name="dice" />
          </Button>
        </div>
        {picked && (
          <p className={s.personaNote} title={`${picked.background}. ${picked.personality}`}>
            {picked.background}
          </p>
        )}
      </div>

      <div className={s.field}>
        <Select label="Objection" value={objectionPick} onChange={(e) => setObjectionPick(e.target.value)}>
          <option value={BUYER_CHOOSES}>Buyer chooses</option>
          {config.chosenObjection.picks.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
          <option value={OWN}>Write my own…</option>
        </Select>
        {objectionPick === OWN && (
          <TextArea
            label="Your objection"
            hideLabel
            autoFocus
            rows={2}
            maxLength={config.chosenObjection.max}
            count={ownObjection.length}
            value={ownObjection}
            placeholder="The buyer raises it in their first reply."
            onChange={(e) => setOwnObjection(e.target.value)}
          />
        )}
      </div>

      {sellSession ? (
        <div className={s.actions}>
          <Button variant="primary" block busy={busy} busyLabel="Starting…" onClick={() => start(shown)}>
            Start new buyer
          </Button>
          <div className={s.secondary}>
            <Button variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
            <Button variant="ghost" onClick={endBuyer}>
              End this buyer
            </Button>
          </div>
        </div>
      ) : (
        <Button variant="primary" block busy={busy} busyLabel="Starting…" onClick={() => start(difficulty)}>
          Start selling
        </Button>
      )}
    </div>
  );
}
