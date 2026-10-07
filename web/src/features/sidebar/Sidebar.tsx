"use client";

import { Notice, Tabs } from "@/components/ui";
import { BuyerSetup } from "@/features/sell/BuyerSetup";
import { useSession } from "@/features/session/SessionContext";
import { config } from "@/lib/config";
import { useUi, type SidebarTab } from "@/state/UiContext";
import { VoiceSettings } from "@/features/voice/VoiceSettings";
import { StatusCard } from "./StatusCard";
import { ToolsGrid } from "./ToolsGrid";
import s from "./Sidebar.module.css";

/** Sell mode only: change the AI buyer once one is live (the first setup sits in the chat area). */
function SetupTab() {
  const { sellSession } = useSession();
  return sellSession ? <BuyerSetup /> : <Notice kind="empty">Buyer settings appear here once you start.</Notice>;
}

export function Sidebar() {
  const { sidebarTab, setSidebarTab } = useUi();
  const { mode } = useSession();
  // Buy mode needs no setup tab: the header already has the switch to selling.
  const tabs: { key: SidebarTab; label: string; content: React.ReactNode }[] = [
    ...(mode === "sell" ? [{ key: "setup" as const, label: "Setup", content: <SetupTab /> }] : []),
    { key: "tools", label: "Tools", content: <ToolsGrid /> },
    { key: "settings", label: "Settings", content: <VoiceSettings /> },
  ];
  // A saved tab that this mode does not have (or an old one) falls back to the first tab.
  const active = tabs.some((t) => t.key === sidebarTab) ? sidebarTab : tabs[0].key;
  return (
    <aside id={config.ids.panels} className={s.sidebar} aria-label="Session sidebar" tabIndex={-1}>
      <StatusCard />
      <Tabs label="Workspace" active={active} onChange={setSidebarTab} tabs={tabs} />
    </aside>
  );
}
