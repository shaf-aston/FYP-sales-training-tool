"use client";

import { useEffect } from "react";
import { useUi } from "@/features/shell/UiContext";
import { useDraft } from "./DraftContext";

const TYPING_TAGS = ["INPUT", "TEXTAREA", "SELECT"];

/** `?` opens help, `/` jumps to the message box. Ignored while typing or when a dialog is open. */
export function useGlobalShortcuts() {
  const { openDialog } = useUi();
  const { inputRef } = useDraft();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const el = document.activeElement as HTMLElement | null;
      if (el && (TYPING_TAGS.includes(el.tagName) || el.isContentEditable)) return;
      if (document.querySelector("dialog[open], [role=dialog]")) return;
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
  }, [openDialog, inputRef]);
}
