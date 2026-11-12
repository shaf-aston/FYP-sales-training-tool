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
      { term: MODE_META.buy.name, text: "you're the customer. A virtual rep sells to you; quiz yourself on what stage the sale is in." },
      { term: MODE_META.sell.name, text: "you're the salesperson. A virtual buyer answers and pushes back." },
    ],
  },
  {
    title: "Reading your progress",
    items: [
      { term: "Buying readiness bar", text: "sell mode: how ready the buyer is to buy. Good questions and listening push it up; pushy or vague lines push it down." },
      { term: "Score", text: "end a sell-mode conversation to get a mark out of 100%." },
    ],
  },
  {
    title: "Learning from a session",
    items: [
      { term: "Walk it back", text: "sell mode, after the call: replay each of your turns with the reasons behind its rating, and redo one." },
      { term: "Say it from memory", text: "fill in the missing move in lines from real sales scripts." },
      { term: "Skill Radar", text: "sell mode: your five skills across every scored session, the one to work on next, and a session that trains it." },
      { term: "Team insights", text: "managers (Account, Team): every member's skill levels, the team's radar, what to coach next, and a CSV." },
      { term: "SOP review", text: "sell mode, Tools: see what your team's sales SOP covers of a good call, then check a real call against it." },
      { term: "Rep's words", text: "buy mode, Tools: hear the call with a top rep's questions (from a real call) or your SOP's, wherever they ask what the script asks. Lines said in their words are tagged. Logged in, save them to use again; a manager can set them for the whole team." },
      { term: "Quiz", text: "buy mode: pick the stage and the next move. Sell mode: rewrite one of your turns and see if it lands better." },
    ],
  },
  {
    title: "Your account (optional)",
    items: [
      { term: "Log in", text: "from the ⋯ menu. Your skill history follows you to any device, and you can save prospects from real calls." },
      { term: "Team", text: "a manager starts one and shares the invite code; reps join with it." },
      { term: "Your data", text: "download everything kept for you, or delete the account (it leaves the nightly backups within 7 days). Call transcripts are never stored." },
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
