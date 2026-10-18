"use client";

import { Fragment, useEffect, useState } from "react";
import { Button, Card, Dialog, Notice } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import { api } from "@/lib/api/client";
import type { Drill } from "@/lib/api/types";
import { config, storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import { grade, isDue, parseSchedule } from "./drillSchedule";
import s from "./DrillsDialog.module.css";

type Load = { status: "loading" } | { status: "error" } | { status: "ready"; shown: Drill[]; dueCount: number };

function DrillCard({ drill, onRated }: { drill: Drill; onRated: () => void }) {
  const [revealed, setRevealed] = useState<ReadonlySet<number>>(new Set());
  const [result, setResult] = useState<boolean | null>(null);
  const total = drill.answers.length;

  const rate = (gotIt: boolean) => {
    const next = grade(parseSchedule(readString(storageKeys.drillSchedule)), drill.id, gotIt, Date.now(), config.drills.intervalsDays);
    writeString(storageKeys.drillSchedule, JSON.stringify(next));
    setResult(gotIt);
    onRated();
  };

  return (
    <Card>
      <div className={s.head}>
        <strong>{drill.label}</strong>
        <span className={s.muted} aria-live="polite">
          {revealed.size} of {total} revealed
        </span>
      </div>
      <p className={s.line}>
        {drill.segments.map((seg, i) => (
          <Fragment key={i}>
            {seg}
            {i < total &&
              (revealed.has(i) ? (
                <span className={s.answer}>{drill.answers[i]}</span>
              ) : (
                <button type="button" className={s.blank} aria-label="Reveal the missing words" onClick={() => setRevealed(new Set(revealed).add(i))}>
                  ?
                </button>
              ))}
          </Fragment>
        ))}
      </p>
      <div className={s.actions} aria-live="polite">
        {revealed.size === total && result === null && (
          <>
            <span>Did you have it?</span>
            <Button variant="primary" onClick={() => rate(true)}>
              Yes
            </Button>
            <Button onClick={() => rate(false)}>Not quite</Button>
          </>
        )}
        {result !== null && <span className={result ? s.kept : s.muted}>{result ? "Kept. Back in a few days." : "Back later today."}</span>}
      </div>
    </Card>
  );
}

function DrillsBody() {
  const { sellSession } = useSession();
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [at, setAt] = useState(0); // one line at a time: the one on screen
  const [rated, setRated] = useState(0);
  const sid = sellSession?.sessionId ?? null;

  useEffect(() => {
    let live = true;
    api
      .sellDrills(sid)
      .then(({ drills }) => {
        if (!live) return;
        const schedule = parseSchedule(readString(storageKeys.drillSchedule));
        const due = drills.filter((d) => isDue(schedule, d.id, Date.now()));
        setLoad({ status: "ready", shown: due.length ? due : drills, dueCount: due.length });
      })
      .catch(() => live && setLoad({ status: "error" }));
    return () => {
      live = false;
    };
  }, [sid, attempt]);

  if (load.status === "loading") return <Notice kind="loading">Loading your lines…</Notice>;
  if (load.status === "error")
    return (
      <Notice kind="error" onRetry={() => {
              setLoad({ status: "loading" });
              setAttempt((n) => n + 1);
            }}>
        The drills couldn&apos;t be loaded just now.
      </Notice>
    );

  const note = !load.shown.length
    ? "There are no lines to practise yet."
    : load.dueCount
      ? `${load.dueCount} lines to practise.`
      : "Nothing is due - here they all are anyway.";

  const total = load.shown.length;
  const drill = load.shown[at];
  const last = at === total - 1;

  return (
    <div className={s.body}>
      <p>Work out the missing part before you click it. {note}</p>
      {drill && (
        <>
          <div className={s.progress}>
            <span>
              Line {at + 1} of {total}
            </span>
            <span className={s.muted}>{rated} rated</span>
          </div>
          <DrillCard key={`${drill.id}-${at}`} drill={drill} onRated={() => setRated((n) => n + 1)} />
          <div className={s.nav}>
            <Button variant="ghost" disabled={at === 0} onClick={() => setAt(at - 1)}>
              Back
            </Button>
            {last ? (
              <span className={s.muted}>That&apos;s every line. Come back tomorrow for the ones you missed.</span>
            ) : (
              <Button variant="primary" onClick={() => setAt(at + 1)}>
                Next line
              </Button>
            )}
          </div>
        </>
      )}
    </div>
  );
}

export function DrillsDialog() {
  const { dialog, closeDialog } = useUi();
  const open = dialog === "drills";
  return (
    <Dialog open={open} onClose={closeDialog} title="Say it from memory" size="lg">
      {open && <DrillsBody />}
    </Dialog>
  );
}
