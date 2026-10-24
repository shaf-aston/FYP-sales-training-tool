"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Button, Icon, Markdown, TextArea, TypingDots, useToast } from "@/components/ui";
import { config } from "@/lib/config";
import { useSession, type ChatMessage } from "@/features/session/SessionContext";
import { ListenButton } from "@/features/voice/VoiceBar";
import { InlineEvaluation } from "@/features/sell/SellDialogs";
import { useUi } from "@/state/UiContext";
import s from "./MessageList.module.css";
import { prefersReducedMotion } from "@/lib/motion";
import { bubbles, highlighted, speakable, typingMs } from "./tone";

/** The AI's badge beside its lines, so it is never mistaken for the mode icons in the header. */
function Avatar() {
  return (
    <span className={s.avatar} aria-hidden="true">
      AI
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

function Editor({ initial, later, onSave, onCancel }: { initial: string; /** messages after this one, replaced on save */ later: number; onSave: (text: string) => Promise<void>; onCancel: () => void }) {
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
      {later > 0 && (
        <p className={s.editNote}>
          Saving replays the chat from here. The {later} message{later === 1 ? "" : "s"} after this one will be replaced.
        </p>
      )}
      <div className={s.editActions}>
        <Button variant="primary" onClick={save} busy={busy} busyLabel="Saving…">
          Save
        </Button>
        <Button variant="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

/** How many of a reply's bubbles show: all at once, or (for the reply just in) one by one, each after its
 * typing dots, so a pause in the line reads as a pause. */
function useReveal(parts: string[], fresh: boolean, answered: boolean, onGrow?: () => void) {
  const [shown, setShown] = useState(() => (fresh && !prefersReducedMotion() ? 1 : parts.length));
  useEffect(() => {
    if (shown > 1) onGrow?.();
    if (shown >= parts.length || answered) return;
    const t = setTimeout(() => setShown((n) => n + 1), typingMs(parts[shown]));
    return () => clearTimeout(t);
  }, [shown, parts, answered, onGrow]);
  return answered ? parts.length : shown; // they replied mid-reveal: the rest shows at once, above their line
}

/** The seller's reply: one bubble per pause in the line, the key thing highlighted. */
function BotBubbles({ text, meta, fresh, answered, onGrow }: { text: string; meta?: string; fresh: boolean; answered: boolean; onGrow?: () => void }) {
  const parts = useMemo(() => (bubbles(text).length ? bubbles(text) : [""]), [text]); // an empty reply still shows its meta
  const shown = useReveal(parts, fresh, answered, onGrow);
  return (
    <div className={s.stack}>
      {parts.slice(0, shown).map((part, i) => (
        <div key={i} className={s.bubble} data-bubble>
          <Markdown text={highlighted(part)} className={s.markdown} />
          {meta && i === parts.length - 1 && <p className={s.meta}>{meta}</p>}
        </div>
      ))}
      {shown < parts.length && (
        <div className={`${s.bubble} ${s.typing}`}>
          <TypingDots label="Assistant is typing" />
        </div>
      )}
    </div>
  );
}

interface ItemProps {
  m: ChatMessage;
  canEdit: boolean;
  editing: boolean;
  /** Messages after this one. */
  later: number;
  /** Absent in sell mode, where turns can't be edited. */
  onEdit?: () => void;
  onSave: (text: string) => Promise<void>;
  onCancel: () => void;
  /** this reply takes the typing bubble's place: only its words fade in, the bubble does not rise again */
  swap?: boolean;
  /** the reply just in: its bubbles show one by one */
  fresh?: boolean;
  /** a bubble of this reply just showed: keep the newest line in view */
  onGrow?: () => void;
}

function Item({ m, canEdit, editing, later, swap, fresh, onEdit, onSave, onCancel, onGrow }: ItemProps) {
  if (m.role === "divider") {
    return (
      <div className={s.divider} role="separator">
        <span>{m.content || "Edited"}</span>
      </div>
    );
  }
  const user = m.role === "user";
  return (
    <div className={`${s.row} ${user ? s.user : s.bot} ${m.historical ? s.historical : ""} ${swap ? s.swap : ""}`}>
      {!user && <Avatar />}
      <div className={s.body}>
      {user ? (
        <div className={s.bubble} data-bubble>
          {editing ? (
            <Editor initial={m.content} later={later} onSave={onSave} onCancel={onCancel} />
          ) : (
            <p className={s.plain}>{m.content}</p>
          )}
          {m.meta && <p className={s.meta}>{m.meta}</p>}
        </div>
      ) : (
        <BotBubbles text={m.content} meta={m.meta} fresh={!!fresh} answered={later > 0} onGrow={onGrow} />
      )}
      {!editing && !m.historical && (
        <div className={s.actions}>
          {!user && <ListenButton text={speakable(m.content)} />}
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
  // The reply that lands as typing stops replaces the typing bubble, so it must not animate in as a new row.
  const [wasTyping, setWasTyping] = useState(typing);
  const [swapId, setSwapId] = useState<string | null>(null);
  // every reply that ever took the typing bubble's place: losing .swap later would replay its rise
  const [swapped, setSwapped] = useState<ReadonlySet<string>>(new Set());
  if (typing !== wasTyping) {
    setWasTyping(typing);
    const id = !typing && messages.at(-1)?.role === "assistant" ? messages.at(-1)!.id : null;
    setSwapId(id);
    if (id) setSwapped((all) => new Set(all).add(id));
  }

  // Pin to the newest line after the browser lays it out; smooth unless reduced motion.
  const pin = useCallback(() => {
    const frame = frameRef.current;
    if (!frame) return;
    const reduced = prefersReducedMotion();
    frame.scrollTo({ top: frame.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, []);
  useEffect(pin, [messages, typing, pin]);

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
        {messages.map((m, i) => (
          <Item
            key={m.id}
            m={m}
            later={messages.slice(i + 1).filter((n) => n.role !== "divider").length}
            canEdit={!typing}
            swap={swapped.has(m.id)}
            fresh={m.id === swapId}
            onGrow={m.id === swapId ? pin : undefined}
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
