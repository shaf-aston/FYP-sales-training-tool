"use client";

// Who is logged in (optional: every feature works logged out). Asks /api/account/me once per page load;
// log in, sign up and log out update it. While logged in, skill history syncs (useSkillSync).

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useToast } from "@/components/ui";
import { api, ApiError } from "@/lib/api/client";
import type { AccountMe, AccountUser, Team } from "@/lib/api/types";
import { forgetSkills, useSkillSync } from "./useSkillSync";
import { writeLocalKnowledge } from "@/features/knowledge/knowledgeStore";

const LOGGED_OUT: AccountMe = { user: null, team: null };

interface AccountValue {
  /** False until the first /me answer, so nothing flashes "Log in" for a logged-in learner. */
  ready: boolean;
  user: AccountUser | null;
  team: Team | null;
  /** Throws ApiError (with `field` for a sign-up field) when the server says no. */
  logIn: (email: string, password: string) => Promise<void>;
  signUp: (email: string, name: string, password: string) => Promise<void>;
  /** Logs out and forgets this device's copy of the account's data, so the next person starts clean. */
  logOut: () => Promise<void>;
  /** Ask the server again (after a team change). */
  refresh: () => Promise<void>;
  /** For a request that needed a login: when it ran out, show the learner as logged out. Returns true if so. */
  handleLoggedOut: (err: unknown) => boolean;
}

const AccountContext = createContext<AccountValue | null>(null);

export function AccountProvider({ children }: { children: ReactNode }) {
  const toast = useToast();
  const [me, setMe] = useState<AccountMe>(LOGGED_OUT);
  const [ready, setReady] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const { user, team } = await api.accountMe();
      setMe({ user, team });
    } catch {
      // No answer: keep what we had.
    }
  }, []);

  // Once per page load. No server answer: carry on logged out, as before accounts existed.
  useEffect(() => {
    let live = true;
    api
      .accountMe()
      .then(({ user, team }) => live && setMe({ user, team }))
      .catch(() => {})
      .finally(() => live && setReady(true));
    return () => {
      live = false;
    };
  }, []);

  useSkillSync(me.user?.id ?? null);

  const logIn = useCallback(async (email: string, password: string) => {
    const { user, team } = await api.accountLogin({ email, password });
    setMe({ user, team });
  }, []);

  const signUp = useCallback(async (email: string, name: string, password: string) => {
    const { user, team } = await api.accountSignup({ email, name, password });
    setMe({ user, team });
  }, []);

  const logOut = useCallback(async () => {
    await api.accountLogout().catch(() => {});
    forgetSkills();
    writeLocalKnowledge(null);   // the product details were this account's
    setMe(LOGGED_OUT);
  }, []);

  const handleLoggedOut = useCallback(
    (err: unknown) => {
      if (!(err instanceof ApiError) || !err.loginRequired) return false;
      setMe(LOGGED_OUT);
      toast("You've been logged out. Log in again to keep going.", "error");
      return true;
    },
    [toast],
  );

  const value = useMemo<AccountValue>(
    () => ({ ready, user: me.user, team: me.team, logIn, signUp, logOut, refresh, handleLoggedOut }),
    [ready, me, logIn, signUp, logOut, refresh, handleLoggedOut],
  );

  return <AccountContext.Provider value={value}>{children}</AccountContext.Provider>;
}

export function useAccount() {
  const ctx = useContext(AccountContext);
  if (!ctx) throw new Error("useAccount must be used inside <AccountProvider>");
  return ctx;
}
