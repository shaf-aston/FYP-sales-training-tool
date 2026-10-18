"use client";

import { useEffect } from "react";
import { useUi } from "@/state/UiContext";
import { useDraft } from "@/state/DraftContext";

const TYPING_TAGS = ["INPUT", "TEXTAREA", "SELECT"];

/** `?` opens help, `/` jumps to the message box, Esc closes an open side panel. Ignored when a dialog is open
 * (it closes itself); `?` and `/` are also ignored while typing. */
export function useGlobalShortcuts() {
  const { openDialog, sidePanel, closeSidePanel } = useUi();
  const { inputRef } = useDraft();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (document.querySelector("dialog[open], [role=dialog]")) return;
      if (e.key === "Escape" && sidePanel) {
        closeSidePanel();
        return;
      }
      const el = document.activeElement as HTMLElement | null;
      if (el && (TYPING_TAGS.includes(el.tagName) || el.isContentEditable)) return;
      if (e.key === "?") {
        e.preventDefault();
        openDialog("help");
      } else if (e.key === "/" && inputRef.current && inputRef.current.offsetParent) {
        e.preventDefault();
        inputRef.current.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [openDialog, inputRef, sidePanel, closeSidePanel]);
}
