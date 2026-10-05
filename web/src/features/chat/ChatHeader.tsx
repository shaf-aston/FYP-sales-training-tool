"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";
import { Button, buttonClass, Icon, useConfirm } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { config } from "@/lib/config";
import { MODE_META } from "@/lib/labels";
import { useUi } from "@/state/UiContext";
import s from "./ChatHeader.module.css";

/** Each seat's icon and where the other seat lives. */
const ROLES = {
  buyer: {
    icon: "buyer",
    switchLabel: "Switch to selling",
    switchTo: config.routes.sell,
  },
  seller: {
    icon: "seller",
    switchLabel: "Switch to buying",
    switchTo: config.routes.practice,
  },
} as const;

export function ChatHeader() {
  const { openDialog } = useUi();
  const { mode, reset, role, prospect } = useSession();
  const modeInfo = MODE_META[mode];
  const confirm = useConfirm();
  const router = useRouter();
  const seat = ROLES[role];
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        triggerRef.current?.focus();
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const items = [...(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];
        const at = items.indexOf(document.activeElement as HTMLElement);
        const step = e.key === "ArrowDown" ? 1 : -1;
        items[(at + step + items.length) % items.length]?.focus();
        e.preventDefault();
      }
    };
    menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  const pick = (dialog: "help" | "feedback") => {
    setMenuOpen(false);
    openDialog(dialog);
  };

  const onReset = async () => {
    setMenuOpen(false);
    const ok = await confirm({
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
          <Icon name={seat.icon} size={14} /> Eloquence
        </p>
        <h1 className={s.title}>{modeInfo.label}</h1>
        <p className={s.subtitle}>{modeInfo.note}</p>
      </div>
      <div className={s.actions}>
        <Link href={seat.switchTo} className={buttonClass("pill", s.switch)} onClick={onSwitch}>
          <Icon name="swap" size={16} /> {seat.switchLabel}
        </Link>
        <Button
          variant="pill"
          className={s.panels}
          aria-controls={config.ids.panels}
          onClick={() => {
            const el = document.getElementById(config.ids.panels);
            el?.scrollIntoView({ behavior: "smooth", block: "start" });
            el?.focus({ preventScroll: true });
          }}
        >
          Panels
        </Button>
        <div className={s.menu} ref={menuRef}>
          <button
            type="button"
            ref={triggerRef}
            className={s.more}
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="More options"
            aria-expanded={menuOpen}
            aria-controls="more-menu"
            aria-haspopup="menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <circle cx="5" cy="12" r="2" />
              <circle cx="12" cy="12" r="2" />
              <circle cx="19" cy="12" r="2" />
            </svg>
          </button>
          {menuOpen && (
            <div id="more-menu" role="menu" aria-label="More options" className={s.popover}>
              <button type="button" role="menuitem" className={s.item} aria-keyshortcuts="?" onClick={() => pick("help")}>
                Help
              </button>
              <button type="button" role="menuitem" className={s.item} onClick={() => pick("feedback")}>
                Feedback
              </button>
              <button type="button" role="menuitem" className={`${s.item} ${s.danger}`} onClick={onReset}>
                Reset session
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
