"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Icon, Notice, Segmented, Select, TextArea, useConfirm } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { api, ApiError } from "@/lib/api/client";
import type { Difficulty, Persona, ProductGroups } from "@/lib/api/types";
import { config } from "@/lib/config";
import { difficultyOptions } from "./options";
import s from "./ProspectSetup.module.css";

const GENERAL = "default";
/** Select value meaning "let the server pick the buyer". */
const SURPRISE = "";

type Groups = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; groups: ProductGroups };

/** Selling seat setup: product, difficulty, which buyer, and an objection to practise. */
export function ProspectSetup() {
  const { prospect, startProspect, exitProspect } = useSession();
  const confirm = useConfirm();
  const [groups, setGroups] = useState<Groups>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [transactional, setTransactional] = useState(GENERAL);
  const [consultative, setConsultative] = useState(GENERAL);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [persona, setPersona] = useState(SURPRISE);
  const [objection, setObjection] = useState("");
  const [busy, setBusy] = useState(false);

  const product = transactional !== GENERAL ? transactional : consultative;

  useEffect(() => {
    let live = true;
    api
      .productGroups()
      .then((r) => live && setGroups({ status: "ready", groups: r.groups }))
      .catch((e) => live && setGroups({ status: "error", message: e instanceof ApiError ? e.message : "Couldn't load the product list." }));
    return () => {
      live = false;
    };
  }, [attempt]);

  // Each product has its own buyers; reload them and clear a pick that no longer exists.
  useEffect(() => {
    let live = true;
    api
      .personas(product)
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

  const shown = prospect?.difficulty ?? difficulty;
  const picked = personas.find((p) => p.name === persona);

  const start = async (d: Difficulty) => {
    setBusy(true);
    await startProspect(d, product, { persona: persona || undefined, objection: objection.trim() || undefined });
    setBusy(false);
  };

  const roll = () => {
    const others = personas.filter((p) => p.name !== persona);
    const pool = others.length ? others : personas;
    if (pool.length) setPersona(pool[Math.floor(Math.random() * pool.length)].name);
  };

  const changeDifficulty = async (d: Difficulty) => {
    if (d === shown) return;
    if (!prospect) return setDifficulty(d);
    const ok = await confirm({
      kicker: "Prospect practice",
      title: "Change difficulty?",
      body: "This ends the current conversation and starts a new one at the new difficulty.",
      confirmLabel: "Reset and change",
    });
    if (!ok) return;
    setDifficulty(d);
    await start(d);
  };

  const options = (list: ProductGroups["transactional"]) =>
    list.map((p) => (
      <option key={p.id} value={p.id}>
        {p.label}
      </option>
    ));

  if (groups.status === "loading") return <Notice kind="loading">Loading products…</Notice>;
  if (groups.status === "error")
    return (
      <Notice
        kind="error"
        action={
          <Button variant="ghost" onClick={retry}>
            Retry
          </Button>
        }
      >
        {groups.message}
      </Notice>
    );

  return (
    <div className={s.stack}>
      <Select
        label="Transactional products"
        value={transactional}
        onChange={(e) => {
          setTransactional(e.target.value);
          if (e.target.value !== GENERAL) setConsultative(GENERAL);
        }}
      >
        <option value={GENERAL}>General practice</option>
        {options(groups.groups.transactional)}
      </Select>
      <Select
        label="Consultative products"
        value={consultative}
        onChange={(e) => {
          setConsultative(e.target.value);
          if (e.target.value !== GENERAL) setTransactional(GENERAL);
        }}
      >
        <option value={GENERAL}>General practice</option>
        {options(groups.groups.consultative)}
      </Select>
      <Segmented label="Difficulty" options={[...difficultyOptions]} value={shown} onChange={changeDifficulty} />

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
        <p className={s.personaNote}>
          <strong>{picked.name}</strong> · {picked.background}. {picked.personality}
        </p>
      )}

      <TextArea
        label="Objection to practise (optional)"
        hint="The buyer raises it in their first reply."
        rows={2}
        maxLength={config.chosenObjection.max}
        count={objection.length}
        value={objection}
        placeholder="Leave empty and the buyer objects when they choose."
        onChange={(e) => setObjection(e.target.value)}
      />
      <div className={s.chips} role="group" aria-label="Common objections">
        {config.chosenObjection.picks.map((o) => (
          <button key={o} type="button" className={s.chip} aria-pressed={objection === o} onClick={() => setObjection(objection === o ? "" : o)}>
            {o}
          </button>
        ))}
      </div>

      {prospect ? (
        <div className={s.actions}>
          <Button variant="primary" block busy={busy} busyLabel="Starting…" onClick={() => start(shown)}>
            New buyer with these settings
          </Button>
          <Button onClick={exitProspect} block>
            End this buyer
          </Button>
        </div>
      ) : (
        <Button variant="primary" block busy={busy} busyLabel="Starting…" onClick={() => start(difficulty)}>
          Start selling
        </Button>
      )}
    </div>
  );
}
