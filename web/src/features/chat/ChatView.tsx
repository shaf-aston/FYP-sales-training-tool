"use client";

import { Card, Eyebrow } from "@/components/ui";
import { ProspectSetup } from "@/features/prospect/ProspectSetup";
import { useSession } from "@/features/session/SessionContext";
import { ChatHeader } from "./ChatHeader";
import { InputBar } from "./InputBar";
import { MessageList } from "./MessageList";
import { useGlobalShortcuts } from "./useGlobalShortcuts";
import s from "./ChatView.module.css";

export function ChatView() {
  useGlobalShortcuts();
  const { mode, prospect } = useSession();
  return (
    <section className={s.view} aria-label="Chat">
      <ChatHeader />
      {mode === "prospect" && !prospect ? (
        <div className={s.setup}>
          <Card tone="accent">
            <Eyebrow>Set up your buyer</Eyebrow>
            <ProspectSetup />
          </Card>
        </div>
      ) : (
        <MessageList />
      )}
      <InputBar />
    </section>
  );
}
