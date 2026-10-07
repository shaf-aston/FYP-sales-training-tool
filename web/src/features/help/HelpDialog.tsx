"use client";

import { useEffect } from "react";
import { Button, Dialog } from "@/components/ui";
import { storageKeys } from "@/lib/config";
import { MODE_META } from "@/lib/labels";
import { readString, storageAvailable, writeString } from "@/lib/storage";
import { useUi } from "@/state/UiContext";
import s from "./HelpDialog.module.css";

const SECTIONS: { title: string; items: { term?: string; text: string; keys?: string }[] }[] = [
  {
    title: "Two ways to practise",
    items: [
      { term: MODE_META.buy.name, text: "you're the customer. The AI sells to you; quiz yourself on what stage the sale is in." },
      { term: MODE_META.sell.name, text: "you're the salesperson. The AI is your buyer." },
    ],
  },
  {
    title: "Reading your progress",
    items: [
      { term: "Buying readiness bar", text: "how ready the buyer is to buy. Good questions and listening push it up; pushy or vague lines push it down." },
      { term: "Score", text: "end a sell-mode conversation to get a mark out of 100%." },
    ],
  },
  {
    title: "Learning from a session",
    items: [
      { term: "Walk it back", text: "replay each of your turns with the reasons behind its rating, and redo one." },
      { term: "Drills", text: "fill in the missing move in lines from real sales scripts." },
      { term: "Quiz", text: "rewrite your weakest turn and see why the new version is better or worse." },
    ],
  },
  {
    title: "Keyboard shortcuts",
    items: [
      { keys: "?", text: "opens this window" },
      { keys: "/", text: "jumps to the message box" },
      { keys: "Shift+Enter", text: "starts a new line" },
      { keys: "Esc", text: "closes any open window" },
    ],
  },
];

export function HelpDialog() {
  const { dialog, openDialog, closeDialog } = useUi();

  // Open once per browser (if storage is blocked the help simply shows each visit).
  useEffect(() => {
    // Show once per browser; never nag when storage is blocked and "seen" can't be remembered.
    if (storageAvailable() && readString(storageKeys.helpSeen) === null) openDialog("help");
  }, [openDialog]);

  const close = () => {
    writeString(storageKeys.helpSeen, "1");
    closeDialog();
  };

  return (
    <Dialog
      open={dialog === "help"}
      onClose={close}
      title="How it works"
      actions={
        <Button variant="primary" onClick={close}>
          Got it
        </Button>
      }
    >
      <div className={s.sections}>
        {SECTIONS.map((sec) => (
          <section key={sec.title}>
            <h3 className={s.heading}>{sec.title}</h3>
            <ul className={s.list}>
              {sec.items.map((it) => (
                <li key={it.term ?? it.keys}>
                  {it.keys && <kbd className={s.kbd}>{it.keys}</kbd>}
                  {it.term && <strong>{it.term}:</strong>} {it.text}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </Dialog>
  );
}
