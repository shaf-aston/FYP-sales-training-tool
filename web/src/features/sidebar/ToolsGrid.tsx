"use client";

import { config } from "@/lib/config";
import type { ReactNode } from "react";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import s from "./Sidebar.module.css";

function Tool({ title, copy, onClick, href, pressed }: { title: string; copy?: string; onClick?: () => void; href?: string; pressed?: boolean }) {
  const body: ReactNode = (
    <>
      <span className={s.toolTitle}>{title}</span>
      {copy && <span className={s.toolCopy}>{copy}</span>}
    </>
  );
  if (href) {
    return (
      // Plain link: the knowledge page is a separate static page, not a route of this app.
      <a className={s.tool} href={href}>
        {body}
      </a>
    );
  }
  return (
    <button type="button" className={`${s.tool} ${pressed ? s.toolOn : ""}`} onClick={onClick} aria-pressed={pressed}>
      {body}
    </button>
  );
}

export function ToolsGrid() {
  const { mode } = useSession();
  const { sidePanel, toggleSidePanel, openDialog } = useUi();
  const sell = mode === "sell";
  return (
    <div className={s.toolGrid}>
      <Tool title="Knowledge" copy="Your product details" href={sell ? `${config.routes.knowledge}?mode=sell` : config.routes.knowledge} />
      {!sell && <Tool title="Coaching" copy="Ask the coach" pressed={sidePanel === "coach"} onClick={() => toggleSidePanel("coach")} />}
      <Tool
        title="Quiz"
        copy={sell ? "Redo your weakest turn" : "Name the stage and next move"}
        pressed={sidePanel === "quiz"}
        onClick={() => toggleSidePanel("quiz")}
      />
      <Tool title="Say it from memory" copy="Fill in the missing line" onClick={() => openDialog("drills")} />
    </div>
  );
}
