"use client";

// The one place skill history meets the account. While logged in: send this device's log up, take the account's
// log merged with anything scored here meanwhile, then send each newly scored or rescored session as the skill
// store records it. Logged out: nothing.
//
// The device log remembers whose it is (storageKeys.skillOwner). Only a log practised logged out, or this same
// account's, goes up: on a shared device the next person never inherits someone else's history. Logging out or
// deleting the account forgets it here (forgetSkills).

import { useEffect } from "react";
import type { SkillEntry, SkillLog } from "@/features/skills/skillLog";
import { skillStore } from "@/features/skills/skillStore";
import { api } from "@/lib/api/client";
import { storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";

/** What the account holds for a session: a rescore changes its scores, not its time, so compare everything. */
const signature = (e: SkillEntry) => JSON.stringify([e.at, e.overall, e.scores]);

/** The account's log plus any session only this device has (scored while the sync was in flight), by time. */
function merged(account: SkillLog, device: SkillLog): SkillLog {
  const known = new Set(account.map((e) => e.sessionId));
  return [...account, ...device.filter((e) => !known.has(e.sessionId))].sort((a, b) => a.at - b.at);
}

/** This device's skill history, its owner and target gone: after logging out or deleting the account. */
export function forgetSkills() {
  skillStore.replace([]);
  writeString(storageKeys.skillOwner, null);
  writeString(storageKeys.skillTarget, null);
}

export function useSkillSync(userId: number | null) {
  useEffect(() => {
    if (userId === null) return;
    let live = true;
    let unsubscribe = () => {};
    /** sessionId -> signature the account already has, so only new or rescored sessions go up. */
    const kept = new Map<string, string>();

    const sendNew = () => {
      const fresh = skillStore.get().filter((e) => kept.get(e.sessionId) !== signature(e));
      if (!fresh.length) return;
      fresh.forEach((e) => kept.set(e.sessionId, signature(e)));
      // A failed send is tried again with the next scored session.
      api.accountSaveSkills(fresh).catch(() => fresh.forEach((e) => kept.delete(e.sessionId)));
    };

    (async () => {
      try {
        const owner = readString(storageKeys.skillOwner);
        const mine = owner === null || owner === String(userId);   // practised logged out, or by this account
        const device = skillStore.get();
        if (mine && device.length) await api.accountSaveSkills(device);
        const { entries } = await api.accountSkills();
        if (!live) return;
        entries.forEach((e) => kept.set(e.sessionId, signature(e)));
        skillStore.replace(mine ? merged(entries, skillStore.get()) : entries);
        writeString(storageKeys.skillOwner, String(userId));
        unsubscribe = skillStore.subscribe(sendNew);
        sendNew();   // anything scored while the sync was in flight
      } catch {
        // Offline or logged out meanwhile: the device log stays as it is; the next load or login tries again.
      }
    })();

    return () => {
      live = false;
      unsubscribe();
    };
  }, [userId]);
}
