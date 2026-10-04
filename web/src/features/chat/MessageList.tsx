"use client";

import { useEffect, useRef, useState } from "react";
import { Button, Markdown, TextArea, TypingDots, useToast } from "@/components/ui";
import { config } from "@/lib/config";
import { useSession, type ChatMessage } from "@/features/session/SessionContext";
import { ListenButton } from "@/features/voice/VoiceBar";
import { InlineEvaluation } from "@/features/prospect/ProspectDialogs";
import s from "./MessageList.module.css";

function TypingBubble() {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setSlow(true), config.slowReplyMs);
    return () => clearTimeout(t);
  }, []);
  return (
    <div className={`${s.row} ${s.bot}`}>
      <div className={`${s.bubble} ${s.typing}`}>
        <TypingDots label="Assistant is typing" />
        {slow && <span className={s.slow}>Still thinking…</span>}
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
  onEdit: () => void;
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
      <div className={s.bubble}>
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
          {user && canEdit && (
            <Button variant="ghost" onClick={onEdit}>
              Edit
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function MessageList() {
  const { messages, typing, mode, edit } = useSession();
  const toast = useToast();
  const [editingId, setEditingId] = useState<string | null>(null);
  const frameRef = useRef<HTMLDivElement>(null);
  const started = messages.some((m) => m.role === "user");

  // Pin to the newest line after the browser lays it out; smooth unless reduced motion.
  useEffect(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
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
      {!started && (
        <div className={s.intro}>
          {mode === "prospect" ? (
            <>
              <h2>Open the call.</h2>
              <p>Example: &ldquo;Thanks for your time. What made you take this call today?&rdquo;</p>
            </>
          ) : (
            <>
              <h2>Tell the salesperson what you need.</h2>
              <p>Example: &ldquo;I&rsquo;m looking for a CRM for my small team.&rdquo;</p>
            </>
          )}
        </div>
      )}
      <div className={s.list} role="log" aria-live="polite" aria-relevant="additions" aria-label="Conversation">
        {messages.map((m) => (
          <Item
            key={m.id}
            m={m}
            canEdit={mode === "seller" && !typing}
            editing={editingId === m.id}
            onEdit={() => startEdit(m.id)}
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
