"use client";

import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui";
import { useSession } from "@/features/session/SessionContext";
import { useDraft } from "@/state/DraftContext";
import { BuyerProfile } from "./BuyerProfile";
import { BuyerSetup } from "./BuyerSetup";
import s from "./BuyerTab.module.css";

/** Sell mode's first sidebar tab: the setup form before a buyer, then the buyer with "New buyer" folded below. */
export function BuyerTab() {
  const { sellSession } = useSession();
  const { inputRef } = useDraft();
  const [newOpen, setNewOpen] = useState(false);
  const formRef = useRef<HTMLElement>(null);
  const close = () => setNewOpen(false);
  // A buyer is ready: go to the message box (on stacked layouts that scrolls back up to the chat).
  const started = () => {
    close();
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  // The form opens below the profile, often out of view.
  useEffect(() => {
    if (newOpen) formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [newOpen]);

  if (!sellSession) return <BuyerSetup onStarted={started} />;
  return (
    <div className={s.tab}>
      <BuyerProfile sellSession={sellSession} />
      {newOpen ? (
        <section ref={formRef} className={s.newBuyer} aria-labelledby="new-buyer-title">
          <h3 id="new-buyer-title" className={s.newTitle}>
            New buyer
          </h3>
          <BuyerSetup onStarted={started} onCancel={close} />
        </section>
      ) : (
        <Button block onClick={() => setNewOpen(true)}>
          New buyer
        </Button>
      )}
    </div>
  );
}
