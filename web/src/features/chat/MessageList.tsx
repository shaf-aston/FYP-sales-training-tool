"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Icon, Markdown, TextArea, TypingDots, useToast } from "@/components/ui";
import { config } from "@/lib/config";
import { useSession, type ChatMessage } from "@/features/session/SessionContext";
import { ListenButton } from "@/features/voice/VoiceBar";
import { InlineEvaluation } from "@/features/sell/SellDialogs";
import { useUi } from "@/state/UiContext";
import s from "./MessageList.module.css";
import { prefersReducedMotion } from "@/lib/motion";

/** The AI's face beside its lines: the person it plays (a seller in buy mode, a buyer in sell mode). */
function Avatar() {
  const { mode } = useSession();
  return (
    <span className={s.avatar} aria-hidden="true">
      <Icon name={mode === "buy" ? "speech" : "person"} size={16} />
    </span>
  );
}

function TypingBubble() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), config.slowReplyMs);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className={`${s.row} ${s.bot}`}>
      <Avatar />
      <div className={s.body}>
        <div className={`${s.bubble} ${s.typing}`}>
          <TypingDots label="Assistant is typing" />
          {slow && <span className={s.slow}>Still thinking…</span>}
        </div>
      </div>
    </div>
  );
}

function Editor({ initial, onSave, onCancel }: { initial: string; onSave: (text: string) => Promise<void>; onCancel: () => void }) {
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);

  const save = async () => {
    const next = text.trim();
    if (!next || next === initial.trim()) return onCancel();
    setBusy(true);
    await onSave(next);
    setBusy(false);
  };

  return (
    <div className={s.editor}>
      <TextArea
        label="Edit your message"
        hideLabel
        autoFocus
        rows={3}
        value={text}
        maxLength={config.maxMessageLength}
        count={text.length}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onCancel();
          if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) void save();
        }}
      />
      <div className={s.editActions}>
        <Button variant="primary" onClick={save} busy={busy} busyLabel="Saving…">
          Save
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

interface ItemProps {
  m: ChatMessage;
  canEdit: boolean;
  editing: boolean;
  /** Absent in sell mode, where turns can't be edited. */
  onEdit?: () => void;
  onSave: (text: string) => Promise<void>;
  onCancel: () => void;
}

function Item({ m, canEdit, editing, onEdit, onSave, onCancel }: ItemProps) {
  if (m.role === "divider") {
    return (
      <div className={s.divider} role="separator">
        <span>{m.content || "Edited"}</span>
      </div>
    );
  }
  const user = m.role === "user";
  return (
    <div className={`${s.row} ${user ? s.user : s.bot} ${m.historical ? s.historical : ""}`}>
      {!user && <Avatar />}
      <div className={s.body}>
      <div className={s.bubble} data-bubble>
        {user ? (
          editing ? (
            <Editor initial={m.content} onSave={onSave} onCancel={onCancel} />
          ) : (
            <p className={s.plain}>{m.content}</p>
          )
        ) : (
          <Markdown text={m.content} className={s.markdown} />
        )}
        {m.meta && <p className={s.meta}>{m.meta}</p>}
      </div>
      {!editing && !m.historical && (
        <div className={s.actions}>
          {!user && <ListenButton text={m.content} />}
          {/* Buy mode only (no onEdit in sell). Always laid out, just hidden while a reply is coming, so the row never grows. */}
          {user && onEdit && (
            <Button
              variant="ghost"
              onClick={onEdit}
              className={canEdit ? undefined : s.unavailable}
              aria-label="Edit this message and replay from here"
              title="Edit"
            >
              <Icon name="pencil" size={16} />
            </Button>
          )}
        </div>
      )}
      </div>
    </div>
  );
}

/** Sell mode before a buyer exists: the setup lives in the sidebar's Buyer tab. */
function SetupPointer() {
  const { showPanels } = useUi();
  const goToSetup = () => showPanels("buyer");
  return (
    <>
      <h2>Set up your buyer.</h2>
      <p>Pick a product, difficulty and buyer in the Buyer tab, then start selling.</p>
      <Button variant="pill" className={s.stackedOnly} onClick={goToSetup}>
        Set up buyer
      </Button>
    </>
  );
}

export function MessageList() {
  const { messages, typing, mode, edit, sellSession } = useSession();
  const toast = useToast();
  const [editingId, setEditingId] = useState<string | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const started = messages.some((m) => m.role === "user");

  // Pin to the newest line after the browser lays it out; smooth unless reduced motion.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const reduced = prefersReducedMotion();
    frame.scrollTo({ top: frame.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, [messages, typing]);

  const startEdit = (id: string) => {
    if (editingId && editingId !== id) return toast("Finish the current edit first.", "info");
    setEditingId(id);
  };

  const save = (m: ChatMessage) => async (text: string) => {
    if (await edit(m.historyIndex, text)) setEditingId(null);
  };

  return (
    <div className={s.frame} ref={frameRef}>
      {/* Folds away on the first message instead of vanishing, so the chat doesn't jump up. */}
      <div className={`${s.introFold} ${started ? s.folded : ""}`} inert={started}>
        <div className={s.intro}>
          {mode === "sell" && !sellSession ? (
            <SetupPointer />
          ) : mode === "sell" ? (
            <>
              <h2>Open the call.</h2>
              <p>Example: &ldquo;Thanks for your time. What made you take this call today?&rdquo;</p>
            </>
          ) : (
            <>
              <h2>You&rsquo;re the customer. The seller speaks first.</h2>
              <p>Answer the way a real buyer would. Push back, ask questions, or go quiet, and watch how the seller handles it.</p>
            </>
          )}
        </div>
      </div>
      <div className={s.list} role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversation">
        {messages.map((m) => (
          <Item
            key={m.id}
            m={m}
            canEdit={!typing}
            editing={editingId === m.id}
            onEdit={mode === "buy" ? () => startEdit(m.id) : undefined}
            onSave={save(m)}
            onCancel={() => setEditingId(null)}
          />
        ))}
        {typing && <TypingBubble />}
        <InlineEvaluation />
      </div>
    </div>
  );
}
