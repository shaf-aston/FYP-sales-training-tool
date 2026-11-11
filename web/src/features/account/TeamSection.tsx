"use client";

import { useEffect, useState } from "react";
import { Badge, Button, Notice, TextInput, useConfirm, useToast } from "@/components/ui";
import { api, errorText } from "@/lib/api/client";
import type { Team, TeamMember } from "@/lib/api/types";
import { config } from "@/lib/config";
import { useAccount } from "./AccountContext";
import s from "./AccountDialog.module.css";

const roleLabel = { manager: "Manager", rep: "Rep" } as const;

/** No team yet: start one (you manage it) or join one with a code. */
function NoTeam() {
  const { refresh, handleLoggedOut } = useAccount();
  const toast = useToast();
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState<"create" | "join" | null>(null);
  const [error, setError] = useState("");

  const run = async (kind: "create" | "join") => {
    setBusy(kind);
    setError("");
    try {
      if (kind === "create") await api.teamCreate(name.trim());
      else await api.teamJoin(code.trim());
      await refresh();
      toast(kind === "create" ? "Team created. Share the invite code with your reps." : "You're in the team.", "success");
    } catch (err) {
      if (!handleLoggedOut(err)) setError(errorText(err, "That didn't go through. Try again."));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className={s.stack}>
      <p className={s.muted}>Practise with your team: a manager starts one and shares the code.</p>
      <div className={s.inline}>
        <TextInput label="Start a team" placeholder="Team name" maxLength={config.account.teamNameMax} value={name} onChange={(e) => setName(e.target.value)} />
        <Button busy={busy === "create"} busyLabel="Creating…" disabled={!name.trim() || !!busy} onClick={() => run("create")}>
          Create
        </Button>
      </div>
      <div className={s.inline}>
        <TextInput label="Or join one" placeholder="Invite code" autoComplete="off" value={code} onChange={(e) => setCode(e.target.value)} />
        <Button busy={busy === "join"} busyLabel="Joining…" disabled={!code.trim() || !!busy} onClick={() => run("join")}>
          Join
        </Button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
    </div>
  );
}

/** In a team: its name, your role, the invite code (managers), who is in it, and leaving. */
function InTeam({ team }: { team: Team }) {
  const { refresh, handleLoggedOut } = useAccount();
  const toast = useToast();
  const confirm = useConfirm();
  const [members, setMembers] = useState<TeamMember[] | null>(null);
  const manager = team.role === "manager";

  useEffect(() => {
    let live = true;
    api
      .team()
      .then((r) => live && setMembers(r.members))
      .catch((err) => live && !handleLoggedOut(err) && setMembers([]));
    return () => {
      live = false;
    };
  }, [team.id, handleLoggedOut]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(team.invite_code ?? "");
      toast("Invite code copied.", "success");
    } catch {
      toast("Couldn't copy. Select the code and copy it.", "error");
    }
  };

  const leave = async () => {
    const ok = await confirm({
      title: `Leave ${team.name}?`,
      body: manager
        ? "If no other manager is left, the rep who joined first takes over the team."
        : "You can join again with the invite code.",
      confirmLabel: "Leave team",
      cancelLabel: "Stay",
      danger: true,
    });
    if (!ok) return;
    try {
      await api.teamLeave();
      await refresh();
      toast(`You left ${team.name}.`, "success");
    } catch (err) {
      if (!handleLoggedOut(err)) toast(errorText(err, "Couldn't leave the team. Try again."), "error");
    }
  };

  return (
    <div className={s.stack}>
      <div className={s.row}>
        <strong className={s.teamName}>{team.name}</strong>
        <Badge tone={manager ? "accent" : "neutral"}>{roleLabel[team.role]}</Badge>
      </div>
      {team.invite_code && (
        <div className={s.row}>
          <span className={s.muted}>Invite code</span>
          <code className={s.code}>{team.invite_code}</code>
          <Button variant="ghost" onClick={copy}>
            Copy
          </Button>
        </div>
      )}
      {members === null ? (
        <Notice kind="loading">Loading the team…</Notice>
      ) : (
        members.length > 0 && (
          <ul className={s.members} aria-label={manager ? "Members" : "Managers"}>
            {members.map((m) => (
              <li key={m.id} className={s.member}>
                <span>
                  {m.name}
                  {m.email && <span className={s.muted}> · {m.email}</span>}
                </span>
                <Badge tone={m.role === "manager" ? "accent" : "neutral"}>{roleLabel[m.role]}</Badge>
              </li>
            ))}
          </ul>
        )
      )}
      <Button variant="ghost" className={s.start} onClick={leave}>
        Leave team
      </Button>
    </div>
  );
}

export function TeamSection() {
  const { team } = useAccount();
  return (
    <section className={s.section} aria-labelledby="account-team">
      <h3 id="account-team" className={s.heading}>
        Team
      </h3>
      {team ? <InTeam team={team} /> : <NoTeam />}
    </section>
  );
}
