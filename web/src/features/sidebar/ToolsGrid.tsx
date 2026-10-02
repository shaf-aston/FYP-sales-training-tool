"use client";

import type { ReactNode } from "react";
import { useSession } from "@/features/session/SessionContext";
import { useUi } from "@/state/UiContext";
import s from "./Sidebar.module.css";

function Tool({ title, copy, onClick, href, pressed }: { title: string; copy: string; onClick?: () => void; href?: string; pressed?: boolean }) {
  const body: ReactNode = (
    <>
      <span className={s.toolTitle}>{title}</span>
      <span className={s.toolCopy}>{copy}</span>
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
  const prospect = mode === "prospect";
  return (
    <div className={s.stack}>
      <div className={s.heading}>
        <h2>Learning tools</h2>
        <p>Open the resource you need without leaving the session flow.</p>
      </div>
      <div className={s.toolGrid}>
        <Tool
          title={prospect ? "Prospect knowledge" : "Knowledge"}
          copy={prospect ? "Review notes tied to your prospect roleplay." : "Browse notes and product details."}
          href={prospect ? "/knowledge/?mode=prospect" : "/knowledge/"}
        />
        {!prospect && (
          <Tool title="Coaching" copy="Get guided next-step advice." pressed={sidePanel === "coach"} onClick={() => toggleSidePanel("coach")} />
        )}
        <Tool title="Quiz" copy="Test your read of the sale and your next move." pressed={sidePanel === "quiz"} onClick={() => toggleSidePanel("quiz")} />
        <Tool title="Say it from memory" copy="Fill the gap before you reveal it." onClick={() => openDialog("drills")} />
        <Tool title="Feedback" copy="Rate the session and suggest fixes." onClick={() => openDialog("feedback")} />
      </div>
    </div>
  );
}
