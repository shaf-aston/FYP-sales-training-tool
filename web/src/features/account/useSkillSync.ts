"use client";

// The one place skill history meets the account. While logged in: send this device's log up, take the account's
// log as the device's, then send each newly scored session as the skill store records it. Logged out: nothing.

import { useEffect } from "react";
import { skillStore } from "@/features/skills/skillStore";
import { api } from "@/lib/api/client";

export function useSkillSync(userId: number | null) {
  useEffect(() => {
    if (userId === null) return;
    let live = true;
    let unsubscribe = () => {};
    /** sessionId -> `at` the account already has, so only new or rescored sessions go up. */
    const kept = new Map<string, number>();

    const sendNew = () => {
      const fresh = skillStore.get().filter((e) => kept.get(e.sessionId) !== e.at);
      if (!fresh.length) return;
      fresh.forEach((e) => kept.set(e.sessionId, e.at));
      // A failed send is tried again with the next scored session.
      api.accountSaveSkills(fresh).catch(() => fresh.forEach((e) => kept.delete(e.sessionId)));
    };

    (async () => {
      try {
        const device = skillStore.get();
        if (device.length) await api.accountSaveSkills(device);
        const { entries } = await api.accountSkills();
        if (!live) return;
        entries.forEach((e) => kept.set(e.sessionId, e.at));
        skillStore.replace(entries);
        unsubscribe = skillStore.subscribe(sendNew);
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
