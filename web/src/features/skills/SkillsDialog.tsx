"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge, Button, Card, Dialog, Notice, Segmented, useConfirm } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { GENERAL_PRODUCT, signed } from "@/features/sell/options";
import { api, errorText } from "@/lib/api/client";
import type { Skill, SkillsRes } from "@/lib/api/types";
import { config, storageKeys } from "@/lib/config";
import { useStoredState } from "@/lib/useStoredState";
import { useUi } from "@/state/UiContext";
import { sentenceCase } from "./radar";
import { averages, change, trend, weakest } from "./skillLog";
import { SkillRadar, Sparkline } from "./SkillRadar";
import { useSkillLog } from "./skillStore";
import s from "./SkillsDialog.module.css";

type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: SkillsRes };

/** The skill list rarely changes: keep it so the dialog opens fully drawn the second time. */
let loaded: SkillsRes | null = null;

const { averageWindow } = config.skills;

/** Skill Radar: every scored sell session's skills, the one to work on next, and a session that trains it. */
export function SkillsDialog() {
  const { dialog, closeDialog } = useUi();
  return (
    <Dialog open={dialog === "skills"} onClose={closeDialog} title="Skill Radar" size="lg">
      {dialog === "skills" && <SkillsBody />}
    </Dialog>
  );
}

function SkillsBody() {
  const [load, setLoad] = useState<Load>(() => (loaded ? { status: "ready", data: loaded } : { status: "loading" }));
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (loaded) return;
    let live = true;
    api
      .sellSkills()
      .then((data) => {
        loaded = data;
        if (live) setLoad({ status: "ready", data });
      })
      .catch((e) => live && setLoad({ status: "error", message: errorText(e, "Couldn't load your skills.") }));
    return () => {
      live = false;
    };
  }, [attempt]);

  if (load.status === "loading") return <Notice kind="loading">Loading your skills…</Notice>;
  if (load.status === "error")
    return (
      <Notice
        kind="error"
        onRetry={() => {
          setLoad({ status: "loading" });
          setAttempt((n) => n + 1);
        }}
      >
        {load.message}
      </Notice>
    );
  return <Radar data={load.data} />;
}

function Radar({ data }: { data: SkillsRes }) {
  const { skills, targets } = data;
  const log = useSkillLog();
  // A saved target the server no longer offers falls back to its default.
  const parseTarget = useCallback((raw: string) => (targets.map(String).includes(raw) ? raw : undefined), [targets]);
  const [targetRaw, setTarget] = useStoredState(storageKeys.skillTarget, String(data.target), parseTarget);
  const target = Number(targetRaw);

  if (!log.length)
    return <Notice kind="empty">Finish a sell session and score it. Your skills show up here, and every session after adds to them.</Notice>;

  const ids = skills.map((k) => k.id);
  const latest = log[log.length - 1].scores;
  const average = averages(log, ids, averageWindow);
  const goals = Object.fromEntries(ids.map((id) => [id, target]));
  // Judged on the recent average, so one bad (or lucky) session does not decide what to train.
  const focus = skills.find((k) => k.id === weakest(average, ids, goals));
  const sessions = log.length;

  return (
    <div className={s.body}>
      <p className={s.muted}>
        {sessions} scored {sessions === 1 ? "session" : "sessions"} on this device. The line is your latest; the shaded shape is your
        average of the last {Math.min(sessions, averageWindow)}; the dashed ring is your target.
      </p>
      <SkillRadar axes={skills} latest={latest} average={average} target={target} />
      {focus ? <Focus skill={focus} score={average[focus.id] ?? 0} target={target} /> : <AllMet />}
      <Segmented
        label="Your target"
        options={targets.map((t) => ({ value: String(t), label: String(t) }))}
        value={String(target)}
        onChange={setTarget}
      />
      <ul className={s.rows}>
        {skills.map((k) => {
          const delta = change(log, k.id, averageWindow);
          const score = latest[k.id];
          return (
            <li key={k.id} className={s.row}>
              <span className={s.name}>{sentenceCase(k.label)}</span>
              <Sparkline values={trend(log, k.id)} />
              {delta && score !== undefined ? (
                <span aria-label={`${signed(delta)} on your recent average`}>
                  <Badge tone={delta > 0 ? "success" : "danger"}>{signed(delta)}</Badge>
                </span>
              ) : (
                <span />
              )}
              <strong className={score !== undefined && score >= target ? s.met : undefined}>{score ?? "–"}</strong>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** The weakest skill against the target (recent average), its tip, and a session that trains it. */
function Focus({ skill, score, target }: { skill: Skill; score: number; target: number }) {
  const { sellSession, startBuyer } = useSession();
  const { closeDialog } = useUi();
  const confirm = useConfirm();
  const [busy, setBusy] = useState(false);
  const practise = async () => {
    const live = sellSession && !sellSession.ended && sellSession.state.turn_count > 0;
    if (
      live &&
      !(await confirm({
        title: `Practise ${skill.label} now?`,
        body: "This ends your current conversation without scoring it, and starts a new buyer.",
        confirmLabel: "Start practice",
        cancelLabel: "Keep talking",
      }))
    )
      return;
    setBusy(true);
    const product = sellSession?.productType ?? GENERAL_PRODUCT;
    const ok = await startBuyer(skill.practice.difficulty, product, { objection: skill.practice.objection });
    setBusy(false);
    if (ok) closeDialog();
  };
  return (
    <Card tone="accent" className={s.focus}>
      <p className={s.eyebrow}>Work on next</p>
      <p className={s.focusName}>
        {sentenceCase(skill.label)} <span className={s.muted}>· averaging {score}, target {target}</span>
      </p>
      <p>{skill.tip}</p>
      <Button variant="primary" busy={busy} busyLabel="Starting…" onClick={practise}>
        Practise {skill.label}
      </Button>
    </Card>
  );
}

function AllMet() {
  return (
    <Card tone="success" className={s.focus}>
      <p className={s.focusName}>Every skill is at your target.</p>
      <p>Raise the target to keep stretching.</p>
    </Card>
  );
}
