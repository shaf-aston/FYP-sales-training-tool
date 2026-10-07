"use client";

import { ChatHeader } from "./ChatHeader";
import { InputBar } from "./InputBar";
import { MessageList } from "./MessageList";
import { useGlobalShortcuts } from "./useGlobalShortcuts";
import s from "./ChatView.module.css";

export function ChatView() {
  useGlobalShortcuts();
  return (
    <section className={s.view} aria-label="Chat">
      <ChatHeader />
      <MessageList />
      <InputBar />
    </section>
  );
}
