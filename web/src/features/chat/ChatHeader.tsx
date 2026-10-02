"use client";

import { useEffect, useRef, useState } from "react";
import { Button, useConfirm } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import s from "./ChatHeader.module.css";

export function ChatHeader() {
  const { openDialog } = useUi();
  const { reset } = useSession();
  const confirm = useConfirm();
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

  return (
    <header className={s.header}>
      <div className={s.copy}>
        <p className={s.eyebrow}>Practice workspace</p>
        <h1 className={s.title}>Eloquence</h1>
        <p className={s.subtitle}>
          Run a practice conversation, watch your stage progress, and ask for live coaching when you need it.
        </p>
      </div>
      <div className={s.actions}>
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
