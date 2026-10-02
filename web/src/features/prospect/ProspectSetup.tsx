"use client";

import { useCallback, useEffect, useState } from "react";
import { Button, Notice, Segmented, Select, useConfirm } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { api, ApiError } from "@/lib/api/client";
import type { Difficulty, ProductGroups } from "@/lib/api/types";
import { difficultyOptions } from "./options";
import s from "./ProspectSetup.module.css";

const GENERAL = "default";

type Groups = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; groups: ProductGroups };

/** Mode tab: pick a product and difficulty, then start (or exit) prospect practice. */
export function ProspectSetup() {
  const { prospect, startProspect, exitProspect } = useSession();
  const confirm = useConfirm();
  const [groups, setGroups] = useState<Groups>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [transactional, setTransactional] = useState(GENERAL);
  const [consultative, setConsultative] = useState(GENERAL);
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [busy, setBusy] = useState(false);

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

  const retry = useCallback(() => {
    setGroups({ status: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  const product = transactional !== GENERAL ? transactional : consultative;
  const shown = prospect?.difficulty ?? difficulty;

  const start = async (d: Difficulty) => {
    setBusy(true);
    await startProspect(d, product);
    setBusy(false);
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
      {prospect ? (
        <Button onClick={exitProspect} block>
          Exit prospect practice
        </Button>
      ) : (
        <Button variant="primary" block busy={busy} busyLabel="Starting…" onClick={() => start(difficulty)}>
          Start prospect practice
        </Button>
      )}
      <Notice kind="empty">Stage controls are not available in prospect practice.</Notice>
    </div>
  );
}
