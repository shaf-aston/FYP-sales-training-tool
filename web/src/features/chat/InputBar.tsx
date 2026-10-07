"use client";

import { useLayoutEffect, type KeyboardEvent } from "react";
import { Button } from "@/components/ui";
import { config } from "@/lib/config";
import { useSession } from "@/features/session/SessionContext";
import { VoiceBar } from "@/features/voice/VoiceBar";
import { useDraft } from "@/state/DraftContext";
import s from "./InputBar.module.css";

export function InputBar() {
  const { draft, setDraft, submit, inputRef } = useDraft();
  const { typing, sellSession, mode } = useSession();
  const ended = mode === "sell" && !!sellSession?.ended;
  const noBuyer = mode === "sell" && !sellSession;
  const placeholder = noBuyer
    ? "Set up your buyer first."
    : ended
      ? "Conversation over. Reset to go again."
      : "Type your reply…";

  // Grow with the text; CSS caps the height at --input-max-height and scrolls beyond.
  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [draft, inputRef]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      if (!typing && !ended && !noBuyer) void submit();
    }
  };

  return (
    <div className={s.bar}>
      <VoiceBar />
      <div className={s.row}>
        <label htmlFor="message-input" className="sr-only">
          Your message
        </label>
        <textarea
          id="message-input"
          ref={inputRef}
          className={s.input}
          rows={1}
          value={draft}
          maxLength={config.maxMessageLength}
          placeholder={placeholder}
          aria-keyshortcuts="/"
          disabled={ended || noBuyer}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <Button variant="primary" onClick={() => void submit()} disabled={typing || ended || noBuyer || !draft.trim()}>
          Send
        </Button>
      </div>
    </div>
  );
}
