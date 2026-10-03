"use client";

// Page layout: [coach or quiz panel] | chat | [prospect panel] | sidebar.
// Everything sits on frosted glass over the night-city film.

import { ConfirmProvider, ToastProvider } from "@/components/ui";
import { AmbientFilm } from "@/components/film/AmbientFilm";
import { ChatView } from "@/features/chat/ChatView";
import { DraftProvider } from "@/state/DraftContext";
import { CoachPanel } from "@/features/coach/CoachPanel";
import { FeedbackDialog } from "@/features/feedback/FeedbackDialog";
import { HelpDialog } from "@/features/help/HelpDialog";
import { ProspectDialogs } from "@/features/prospect/ProspectDialogs";
import { ProspectPanel } from "@/features/prospect/ProspectPanel";
import { QuizPanel } from "@/features/quiz/QuizPanel";
import { SessionProvider, useSession, type LearnerRole } from "@/features/session/SessionContext";
import { Sidebar } from "@/features/sidebar/Sidebar";
import { VoiceProvider } from "@/features/voice/VoiceContext";
import { UiProvider, useUi } from "@/state/UiContext";
import s from "./AppShell.module.css";

function Layout() {
  const { sidePanel } = useUi();
  const { mode } = useSession();
  const cls = [s.grid, sidePanel && s.withSide, mode === "prospect" && s.withProspect].filter(Boolean).join(" ");
  return (
    <div className={s.shell}>
      <main className={cls}>
        {sidePanel === "coach" && <CoachPanel />}
        {sidePanel === "quiz" && <QuizPanel />}
        <ChatView />
        {mode === "prospect" && <ProspectPanel />}
        <Sidebar />
      </main>
      <HelpDialog />
      <FeedbackDialog />
      <ProspectDialogs />
    </div>
  );
}

/** `role` is the learner's seat: /practice/ plays the buyer, /practice/sell/ does the selling. */
export function AppShell({ role }: { role: LearnerRole }) {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <UiProvider>
          <SessionProvider role={role}>
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
