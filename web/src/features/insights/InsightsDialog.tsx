"use client";

import { useEffect, useState } from "react";
import { Badge, Card, Dialog, Notice, Segmented } from "@/components/ui";
import { useAccount } from "@/features/account/AccountContext";
import { SkillRadar } from "@/features/skills/SkillRadar";
import { sentenceCase } from "@/features/skills/radar";
import { api, errorText } from "@/lib/api/client";
import type { MemberInsight, TeamInsights } from "@/lib/api/types";
import { useUi } from "@/state/UiContext";
import s from "./InsightsDialog.module.css";

/** `now` is when the insights arrived, so "practised 3 days ago" is measured from then (render stays pure). */
type Load = { status: "loading" } | { status: "error"; message: string } | { status: "ready"; data: TeamInsights; now: number };

const DAY_MS = 86_400_000;

/** "today", "yesterday", "5 days ago", or "never". */
function practised(at: number | null, now: number): string {
  if (at === null) return "never";
  const days = Math.floor((now - at) / DAY_MS);
  return days <= 0 ? "today" : days === 1 ? "yesterday" : `${days} days ago`;
}

/** Manager insights: the team's skill levels on the radar, coaching guidelines, and every member's levels. */
export function InsightsDialog() {
  const { dialog, closeDialog } = useUi();
  return (
    <Dialog open={dialog === "insights"} onClose={closeDialog} title="Team insights" size="lg">
      {dialog === "insights" && <InsightsBody />}
    </Dialog>
  );
}

function InsightsBody() {
  const { team, handleLoggedOut } = useAccount();
  const [target, setTarget] = useState<number | undefined>();
  const [load, setLoad] = useState<Load>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .teamInsights(target)
      .then((data) => live && setLoad({ status: "ready", data, now: Date.now() }))
      .catch((err) => live && !handleLoggedOut(err) && setLoad({ status: "error", message: errorText(err, "Couldn't load the team's insights.") }));
    return () => {
      live = false;
    };
  }, [target, attempt, handleLoggedOut]);

  if (load.status === "loading") return <Notice kind="loading">Adding up the team&apos;s sessions…</Notice>;
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

  const { data, now } = load;
  const label = Object.fromEntries(data.skills.map((k) => [k.id, sentenceCase(k.label)]));
  const ranked = data.members.some((m) => m.judged);

  return (
    <div className={s.body}>
      <p className={s.muted}>
        {team?.name}: levels are each member&apos;s average over their recent scored sessions. Ask members to log in so their
        practice counts here.
      </p>
      {ranked ? (
        <SkillRadar axes={data.skills} latest={data.team} average={data.team} target={data.target} />
      ) : (
        <Notice kind="empty">No one has enough scored sessions yet. Levels appear after each member&apos;s second session.</Notice>
      )}
      <Segmented
        label="Target"
        options={data.targets.map((t) => ({ value: String(t), label: String(t) }))}
        value={String(data.target)}
        onChange={(v) => {
          setLoad({ status: "loading" });
          setTarget(Number(v));
        }}
      />
      {data.guidelines.length > 0 && (
        <Card tone="accent" className={s.guidelines}>
          <p className={s.eyebrow}>Coach next</p>
          <ul>
            {data.guidelines.map((g) => (
              <li key={g}>{g}</li>
            ))}
          </ul>
        </Card>
      )}
      <ul className={s.members} aria-label="Members">
        {data.members.map((m) => (
          <Member key={m.user_id} member={m} skills={data.skills.map((k) => k.id)} label={label} target={data.target} now={now} />
        ))}
      </ul>
      <a className={s.export} href="/api/team/insights.csv" download>
        Download as a spreadsheet (CSV)
      </a>
    </div>
  );
}

function Member({ member: m, skills, label, target, now }: { member: MemberInsight; skills: string[]; label: Record<string, string>; target: number; now: number }) {
  return (
    <li className={s.member}>
      <div className={s.who}>
        <strong>{m.name}</strong>
        <span className={s.muted}>
          {m.sessions} {m.sessions === 1 ? "session" : "sessions"} · practised {practised(m.last_at, now)}
        </span>
      </div>
      <div className={s.levels}>
        {skills.map((id) =>
          m.levels[id] === undefined ? null : (
            <span key={id} className={s.level} title={label[id]}>
              <span className={s.levelName}>{label[id]}</span>
              <span className={m.levels[id] >= target ? s.met : s.below}>{m.levels[id]}</span>
            </span>
          ),
        )}
      </div>
      {m.weakest ? <Badge tone="warning">Work on {label[m.weakest].toLowerCase()}</Badge> : !m.judged && <Badge>Too early to tell</Badge>}
    </li>
  );
}
