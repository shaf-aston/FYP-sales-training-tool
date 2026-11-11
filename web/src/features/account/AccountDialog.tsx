"use client";

import { Button, Dialog, useToast } from "@/components/ui";
import { useUi } from "@/state/UiContext";
import { useAccount } from "./AccountContext";
import { AuthForm } from "./AuthForm";
import { DataSection } from "./DataSection";
import { TeamSection } from "./TeamSection";
import s from "./AccountDialog.module.css";

/** Logged in: who you are, your team, your data, log out. */
function AccountPanel({ onClose }: { onClose: () => void }) {
  const { user, logOut } = useAccount();
  const toast = useToast();
  if (!user) return null;

  const out = async () => {
    await logOut();
    onClose();
    toast("Logged out. Your practice keeps working on this device.", "info");
  };

  return (
    <div className={s.panel}>
      <div className={s.who}>
        <strong className={s.name}>{user.name}</strong>
        <span className={s.muted}>{user.email}</span>
      </div>
      <TeamSection />
      <DataSection onDeleted={onClose} />
      <Button variant="ghost" className={s.start} onClick={out}>
        Log out
      </Button>
    </div>
  );
}

/** The ⋯ menu's "Log in" / "Account" window. */
export function AccountDialog() {
  const { dialog, closeDialog } = useUi();
  const { user } = useAccount();
  const toast = useToast();
  const open = dialog === "account";

  const loggedIn = (mode: "login" | "signup") => {
    closeDialog();
    toast(mode === "signup" ? "Account created. Your skill history now follows you." : "Logged in. Your skill history follows you.", "success");
  };

  return (
    <Dialog open={open} onClose={closeDialog} title={user ? "Your account" : "Account"} size="sm">
      {open && (user ? <AccountPanel onClose={closeDialog} /> : <AuthForm onDone={loggedIn} />)}
    </Dialog>
  );
}
