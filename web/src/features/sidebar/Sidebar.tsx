"use client";

import { Tabs } from "@/components/ui";
import { BuyerTab } from "@/features/sell/BuyerTab";
import { useSession } from "@/features/session/SessionContext";
import { config } from "@/lib/config";
import { useUi, type SidebarTab } from "@/state/UiContext";
import { VoiceSettings } from "@/features/voice/VoiceSettings";
import { StageCard } from "./StageCard";
import { ToolsGrid } from "./ToolsGrid";
import s from "./Sidebar.module.css";

export function Sidebar() {
  const { sidebarTab, setSidebarTab } = useUi();
  const { mode } = useSession();
  const sell = mode === "sell";
  // Buy mode has no buyer tab: the header already has the switch to selling.
  const tabs: { key: SidebarTab; label: string; content: React.ReactNode }[] = [
    ...(sell ? [{ key: "buyer" as const, label: "Buyer", content: <BuyerTab /> }] : []),
    { key: "tools", label: "Tools", content: <ToolsGrid /> },
    { key: "settings", label: "Settings", content: <VoiceSettings /> },
  ];
  // A saved tab that this mode does not have (or an old one) falls back to the first tab.
  const active = tabs.some((t) => t.key === sidebarTab) ? sidebarTab : tabs[0].key;
  return (
    <aside id={config.ids.panels} className={s.sidebar} aria-label="Session sidebar" tabIndex={-1}>
      {/* Sell mode names the buyer and their state in the Buyer tab, so the card would repeat it. */}
      {!sell && <StageCard />}
      <Tabs label="Workspace" active={active} onChange={setSidebarTab} tabs={tabs} />
    </aside>
  );
}
