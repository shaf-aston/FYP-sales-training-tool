"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Button, buttonClass, Icon, useConfirm } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { config } from "@/lib/config";
import { useUi } from "@/state/UiContext";
import s from "./ChatHeader.module.css";

/** What each seat means, said plainly, and where the other seat lives. */
const ROLES = {
  buyer: {
    icon: "buyer",
    eyebrow: "You are the buyer",
    subtitle: "The AI salesperson sells to you. Push back, ask about price, and watch how it handles you.",
    switchLabel: "Switch to selling",
    switchTo: config.routes.sell,
  },
  seller: {
    icon: "seller",
    eyebrow: "You are the seller",
    subtitle: "The AI plays the buyer. Pick who they are and what they object to, then make the sale.",
    switchLabel: "Switch to buying",
    switchTo: config.routes.practice,
  },
} as const;

export function ChatHeader() {
  const { openDialog } = useUi();
  const { reset, role, prospect } = useSession();
  const confirm = useConfirm();
  const router = useRouter();
  const seat = ROLES[role];
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setMenuOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const onReset = async () => {
    setMenuOpen(false);
    const ok = await confirm({
      kicker: "Reset session",
      title: "Clear this practice session?",
      body: "This wipes the conversation and starts again. You cannot undo it.",
      confirmLabel: "Reset session",
      cancelLabel: "Keep session",
      danger: true,
    });
    if (ok) await reset();
  };

  // Leaving the selling page drops the live buyer; ask first if the learner has started.
  const onSwitch = async (e: ReactMouseEvent<HTMLAnchorElement>) => {
    if (!prospect || prospect.state.turn_count < 1) return;
    e.preventDefault();
    const ok = await confirm({
      kicker: "Switch role",
      title: "Leave this buyer?",
      body: "Switching to the buyer seat ends this practice conversation.",
      confirmLabel: "Switch role",
      cancelLabel: "Keep selling",
    });
    if (ok) router.push(seat.switchTo);
  };

  return (
    <header className={s.header}>
      <div className={s.copy}>
        <p className={s.eyebrow}>
          <Icon name={seat.icon} size={14} /> {seat.eyebrow}
        </p>
        <h1 className={s.title}>Eloquence</h1>
        <p className={s.subtitle}>{seat.subtitle}</p>
      </div>
      <div className={s.actions}>
        <Link href={seat.switchTo} className={buttonClass("pill", s.switch)} onClick={onSwitch}>
          <Icon name="swap" size={16} /> {seat.switchLabel}
        </Link>
        <Button variant="pill" onClick={() => openDialog("help")} aria-keyshortcuts="?" title="How it works (press ?)">
          Help
        </Button>
        <Button variant="pill" onClick={() => openDialog("feedback")} title="Share quick product feedback">
          Feedback
        </Button>
        <div className={s.menu} ref={menuRef}>
          <Button
            variant="pill"
            onClick={() => setMenuOpen((o) => !o)}
            aria-expanded={menuOpen}
            aria-controls="reset-menu"
            aria-haspopup="true"
          >
            More
          </Button>
          {menuOpen && (
            <div id="reset-menu" className={s.popover}>
              <button type="button" className={s.item} onClick={onReset}>
                Reset session
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
