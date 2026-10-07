"use client";

// Page layout: [coach or quiz panel] | chat | [buyer panel, sell mode] | sidebar.
// Everything sits on frosted glass over the night-city film.

import { ConfirmProvider, ToastProvider } from "@/components/ui";
import { AmbientFilm } from "@/components/film/AmbientFilm";
import { ChatView } from "@/features/chat/ChatView";
import { DraftProvider } from "@/state/DraftContext";
import { CoachPanel } from "@/features/coach/CoachPanel";
import { FeedbackDialog } from "@/features/feedback/FeedbackDialog";
import { HelpDialog } from "@/features/help/HelpDialog";
import { SellDialogs } from "@/features/sell/SellDialogs";
import { BuyerPanel } from "@/features/sell/BuyerPanel";
import { QuizPanel } from "@/features/quiz/QuizPanel";
import { SessionProvider, useSession, type Mode } from "@/features/session/SessionContext";
import { Sidebar } from "@/features/sidebar/Sidebar";
import { VoiceProvider } from "@/features/voice/VoiceContext";
import { UiProvider, useUi } from "@/state/UiContext";
import s from "./AppShell.module.css";

function Layout() {
  const { sidePanel } = useUi();
  const { mode, sellSession } = useSession();
  const cls = [s.grid, sidePanel && s.withSide, mode === "sell" && sellSession && s.withBuyer].filter(Boolean).join(" ");
  return (
    <div className={s.shell}>
      <main className={cls}>
        {sidePanel === "coach" && <CoachPanel />}
        {sidePanel === "quiz" && <QuizPanel />}
        <ChatView />
        {mode === "sell" && <BuyerPanel />}
        <Sidebar />
      </main>
      <HelpDialog />
      <FeedbackDialog />
      <SellDialogs />
    </div>
  );
}

/** `mode` is what the learner does: /buy/ is buy mode, /sell/ is sell mode. */
export function AppShell({ mode }: { mode: Mode }) {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <UiProvider>
          <SessionProvider mode={mode}>
            <DraftProvider>
              <VoiceProvider>
                <AmbientFilm />
                <Layout />
              </VoiceProvider>
            </DraftProvider>
          </SessionProvider>
        </UiProvider>
      </ConfirmProvider>
    </ToastProvider>
  );
}
