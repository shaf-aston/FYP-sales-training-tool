"use client";

import { useEffect } from "react";
import { Dialog } from "@/components/ui";
import { storageKeys } from "@/lib/config";
import { writeString } from "@/lib/storage";
import { useUi } from "@/features/shell/UiContext";
import s from "./HelpDialog.module.css";

const SECTIONS: { title: string; items: { term?: string; text: string; keys?: string }[] }[] = [
  {
    title: "Two ways to practise",
    items: [
      { term: "Seller bot", text: "you are the customer. An AI salesperson talks to you, and you can quiz yourself on what stage the sale is in." },
      { term: "Prospect practice", text: "you are the salesperson. An AI buyer answers you." },
    ],
  },
  {
    title: "Reading your progress",
    items: [
      { term: "Buying readiness bar", text: "how ready the buyer is to buy. Good questions and listening push it up; pushy or vague lines push it down." },
      { term: "Score", text: "when you end a practice, it rates the whole conversation out of 100%." },
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
      { keys: "Esc", text: "closes any open window" },
    ],
  },
];

export function HelpDialog() {
  const { dialog, openDialog, closeDialog } = useUi();

  // Open once per browser. If storage is blocked we cannot remember a visit, so never nag.
  useEffect(() => {
    try {
      if (localStorage.getItem(storageKeys.helpSeen)) return;
    } catch {
      return;
    }
    openDialog("help");
  }, [openDialog]);

  const close = () => {
    writeString(storageKeys.helpSeen, "1");
    closeDialog();
  };

  return (
    <Dialog open={dialog === "help"} onClose={close} title="How it works">
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
