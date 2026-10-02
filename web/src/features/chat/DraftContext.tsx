"use client";

// The text in the message box. Shared so voice dictation can write into it and send it.

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";
import { useSession } from "@/features/session/SessionContext";

interface DraftValue {
  draft: string;
  setDraft: (text: string) => void;
  /** Append dictated words with a separating space. */
  append: (text: string) => void;
  /** Send the current draft; restores it if the send was rolled back. */
  submit: () => Promise<void>;
  /** The textarea, so shortcuts and voice can focus it. */
  inputRef: React.RefObject<HTMLTextAreaElement | null>;
}

const DraftContext = createContext<DraftValue | null>(null);

export function DraftProvider({ children }: { children: ReactNode }) {
  const { send } = useSession();
  const [draft, setDraft] = useState("");
  const draftRef = useRef("");
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  const update = useCallback((text: string) => {
    draftRef.current = text;
    setDraft(text);
  }, []);

  const append = useCallback((text: string) => update(draftRef.current ? `${draftRef.current.trimEnd()} ${text}` : text), [update]);

  const submit = useCallback(async () => {
    const text = draftRef.current;
    if (!text.trim()) return;
    update("");
    const res = await send(text);
    if (!res.ok && res.restore && !draftRef.current) update(res.restore);
  }, [send, update]);

  const value = useMemo(() => ({ draft, setDraft: update, append, submit, inputRef }), [draft, update, append, submit]);
  return <DraftContext.Provider value={value}>{children}</DraftContext.Provider>;
}

export function useDraft() {
  const ctx = useContext(DraftContext);
  if (!ctx) throw new Error("useDraft must be used inside <DraftProvider>");
  return ctx;
}
