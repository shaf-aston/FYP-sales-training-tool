"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Button, buttonClass, Icon, useConfirm } from "@/components/ui";
import { useAccount } from "@/features/account/AccountContext";
import { useSession } from "@/features/session/SessionContext";
import { api } from "@/lib/api/client";
import type { BuyProduct, ScriptStep } from "@/lib/api/types";
import { config } from "@/lib/config";
import { MODE_META, STAGE_STEPS, stageIndex } from "@/lib/labels";
import { useUi } from "@/state/UiContext";
import s from "./ChatHeader.module.css";

/** Each mode's icon and the page of the other mode. */
const MODES = {
  buy: { icon: "person", switchTo: config.routes.sell },
  sell: { icon: "speech", switchTo: config.routes.buy },
} as const;

export function ChatHeader() {
  const { openDialog, showPanels, sidePanel } = useUi();
  const { mode, reset, jumpTo, switchProduct, buySessionId, buyProduct, stage, messages } = useSession();
  const account = useAccount();
  // Each product runs its own script, so steps are kept with the product they came from.
  const [loaded, setLoaded] = useState<{ product: string | null; steps: ScriptStep[] }>({ product: null, steps: [] });
  const steps = loaded.product === buyProduct ? loaded.steps : [];
  const [products, setProducts] = useState<BuyProduct[]>([]);
  const at = stageIndex(stage);
  // Phones and tablets: the sidebar sits below the chat, so its button carries the stage.
  // Not while the quiz is open: it asks which stage the sale is in.
  const staged = mode === "buy" && at >= 0 && sidePanel !== "quiz";
  const panelsLabel = staged ? `Stage ${at + 1}/${STAGE_STEPS.length}` : "Panels";
  const words = MODE_META[mode];
  const confirm = useConfirm();
  const here = MODES[mode];
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDown = (e: MouseEvent) => {
      if (!menuRef.current?.contains(e.target as Node)) setMenuOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMenuOpen(false);
        triggerRef.current?.focus();
      } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        const items = [...(menuRef.current?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])];
        const at = items.indexOf(document.activeElement as HTMLElement);
        const step = e.key === "ArrowDown" ? 1 : -1;
        items[(at + step + items.length) % items.length]?.focus();
        e.preventDefault();
      }
    };
    menuRef.current?.querySelector<HTMLElement>('[role="menuitem"]')?.focus();
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  // Buy mode: what the rep can sell, loaded once the menu first opens.
  useEffect(() => {
    if (!menuOpen || mode !== "buy" || products.length) return;
    api.buyProducts().then((r) => setProducts(r.products)).catch(() => {});
  }, [menuOpen, mode, products.length]);

  // Buy mode: the script's steps, loaded once the menu first opens, to start a fresh call at one.
  useEffect(() => {
    if (!menuOpen || mode !== "buy" || !buySessionId || steps.length) return;
    const product = buyProduct;
    api.buySteps(buySessionId).then((r) => setLoaded({ product, steps: r.steps })).catch(() => {});
  }, [menuOpen, mode, buySessionId, buyProduct, steps.length]);

  const onJump = async (step: string) => {
    if (!step) return;
    setMenuOpen(false);
    // Like changing the call type: a call the learner has said something in is cleared only when they agree.
    const ok =
      !messages.some((m) => m.role === "user") ||
      (await confirm({
        title: "Jump to this step?",
        body: "Starts a fresh call at this step. The current chat is cleared.",
        confirmLabel: "Jump",
        cancelLabel: "Keep this call",
      }));
    if (ok) await jumpTo(step);
  };

  const onProduct = async (id: string) => {
    const next = products.find((p) => p.id === id);
    if (!next || id === buyProduct) return;
    setMenuOpen(false);
    const ok = await confirm({
      title: `Practise a ${next.label.toLowerCase()}?`,
      body: `${next.blurb} This starts a fresh call; the current chat is cleared.`,
      confirmLabel: "Start new call",
      cancelLabel: "Keep this call",
    });
    if (ok) await switchProduct(id);
  };

  const pick = (dialog: "help" | "feedback" | "account") => {
    setMenuOpen(false);
    openDialog(dialog);
  };

  const onReset = async () => {
    setMenuOpen(false);
    const ok = await confirm({
      title: "Reset this conversation?",
      body: "This wipes the conversation and starts again. You cannot undo it.",
      confirmLabel: "Reset session",
      cancelLabel: "Keep session",
      danger: true,
    });
    if (ok) await reset();
  };

  return (
    <header className={s.header}>
      <div className={s.copy}>
        <p className={s.eyebrow}>
          <Icon name={here.icon} size={14} /> {words.name}
        </p>
        <h1 className={s.title}>{words.heading}</h1>
        <p className={s.subtitle}>{words.note}</p>
      </div>
      <div className={s.actions}>
        {/* A live call is kept for this tab: coming back picks it up (SessionContext), so leaving needs no warning. */}
        <Link href={here.switchTo} className={buttonClass("pill", s.switch)}>
          <Icon name="swap" size={16} /> {words.switchLabel}
        </Link>
        <Button
          variant="pill"
          className={s.panels}
          aria-controls={config.ids.panels}
          onClick={() => showPanels()}
          aria-label={staged ? `Stage ${at + 1} of ${STAGE_STEPS.length}. Show stage and tools` : undefined}
        >
          {panelsLabel}
        </Button>
        <div className={s.menu} ref={menuRef}>
          <button
            type="button"
            ref={triggerRef}
            className={s.more}
            onClick={() => setMenuOpen((o) => !o)}
            aria-label="More options"
            aria-expanded={menuOpen}
            aria-controls="more-menu"
            aria-haspopup="menu"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
              <circle cx="5" cy="12" r="2" />
              <circle cx="12" cy="12" r="2" />
              <circle cx="19" cy="12" r="2" />
            </svg>
          </button>
          {menuOpen && (
            <div id="more-menu" role="menu" aria-label="More options" className={s.popover}>
              <button type="button" role="menuitem" className={s.item} aria-keyshortcuts="?" onClick={() => pick("help")}>
                Help
              </button>
              <button type="button" role="menuitem" className={s.item} onClick={() => pick("feedback")}>
                Feedback
              </button>
              {account.ready && (
                <button type="button" role="menuitem" className={s.item} onClick={() => pick("account")}>
                  {account.user ? "Account" : "Log in"}
                </button>
              )}
              {mode === "buy" && products.length > 1 && (
                <label className={s.item}>
                  <span className="sr-only">What the rep sells (starts a fresh call)</span>
                  <select
                    role="menuitem"
                    className={s.jump}
                    value=""
                    onChange={(e) => void onProduct(e.target.value)}
                    title="Choose which call the rep runs; starts a fresh call"
                  >
                    <option value="">Call type…</option>
                    {products.map((p) => (
                      <option key={p.id} value={p.id} disabled={p.id === buyProduct}>
                        {p.id === buyProduct ? "✓ " : ""}
                        {p.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              {mode === "buy" && steps.length > 0 && (
                <label className={s.item}>
                  <span className="sr-only">Jump to step (starts a fresh call there)</span>
                  <select
                    role="menuitem"
                    className={s.jump}
                    value=""
                    onChange={(e) => void onJump(e.target.value)}
                    title="Start a fresh call at this step, to test it"
                  >
                    <option value="">Jump to step…</option>
                    {steps.map((st, i) => (
                      <option key={st.id} value={st.id}>
                        {i + 1}. {st.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <button type="button" role="menuitem" className={`${s.item} ${s.danger}`} onClick={onReset}>
                Reset session
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
