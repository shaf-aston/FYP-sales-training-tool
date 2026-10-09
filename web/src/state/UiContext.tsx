"use client";

// Which panels and windows are open. Only one side panel and one dialog at a time.

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { config, storageKeys } from "@/lib/config";
import { useStoredState } from "@/lib/useStoredState";

export type SidePanel = "coach" | "quiz" | null;
export type DialogName = "help" | "review" | "drills" | "evaluation" | "feedback" | null;
/** "buyer" exists only in sell mode; the sidebar falls back to its first tab when the saved one is missing or old. */
export type SidebarTab = "buyer" | "tools" | "settings";

interface UiValue {
  sidePanel: SidePanel;
  toggleSidePanel: (p: Exclude<SidePanel, null>) => void;
  closeSidePanel: () => void;
  dialog: DialogName;
  openDialog: (d: Exclude<DialogName, null>) => void;
  closeDialog: () => void;
  sidebarTab: SidebarTab;
  setSidebarTab: (t: SidebarTab) => void;
  /** Scroll to the sidebar (below the chat on phones) and focus it, optionally on a tab. */
  showPanels: (tab?: SidebarTab) => void;
}

const UiContext = createContext<UiValue | null>(null);

const TABS: SidebarTab[] = ["buyer", "tools", "settings"];
const parseTab = (raw: string) => (TABS.includes(raw as SidebarTab) ? (raw as SidebarTab) : undefined);

export function UiProvider({ children }: { children: ReactNode }) {
  const [sidePanel, setSidePanel] = useState<SidePanel>(null);
  const [dialog, setDialog] = useState<DialogName>(null);
  const [sidebarTab, setSidebarTab] = useStoredState<SidebarTab>(storageKeys.sidebarTab, "buyer", parseTab); // buy mode has no "buyer" tab, so Sidebar falls back

  const value = useMemo<UiValue>(
    () => ({
      sidePanel,
      toggleSidePanel: (p) => setSidePanel((cur) => (cur === p ? null : p)),
      closeSidePanel: () => setSidePanel(null),
      dialog,
      openDialog: setDialog,
      closeDialog: () => setDialog(null),
      sidebarTab,
      setSidebarTab,
      showPanels: (tab) => {
        if (tab) setSidebarTab(tab);
        const el = document.getElementById(config.ids.panels);
        el?.scrollIntoView({ behavior: "smooth", block: "start" });
        el?.focus({ preventScroll: true });
      },
    }),
    [sidePanel, dialog, sidebarTab, setSidebarTab],
  );

  return <UiContext.Provider value={value}>{children}</UiContext.Provider>;
}

export function useUi() {
  const ctx = useContext(UiContext);
  if (!ctx) throw new Error("useUi must be used inside <UiProvider>");
  return ctx;
}
