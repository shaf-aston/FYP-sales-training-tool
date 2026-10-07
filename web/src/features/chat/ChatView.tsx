"use client";

import { Card, Eyebrow } from "@/components/ui";
import { BuyerSetup } from "@/features/sell/BuyerSetup";
import { useSession } from "@/features/session/SessionContext";
import { ChatHeader } from "./ChatHeader";
import { InputBar } from "./InputBar";
import { MessageList } from "./MessageList";
import { useGlobalShortcuts } from "./useGlobalShortcuts";
import s from "./ChatView.module.css";

export function ChatView() {
  useGlobalShortcuts();
  const { mode, sellSession } = useSession();
  return (
    <section className={s.view} aria-label="Chat">
      <ChatHeader />
      {mode === "sell" && !sellSession ? (
        <div className={s.setup}>
          <Card tone="accent">
            <Eyebrow>Set up your buyer</Eyebrow>
            <BuyerSetup />
          </Card>
        </div>
      ) : (
        <MessageList />
      )}
      <InputBar />
    </section>
  );
}
