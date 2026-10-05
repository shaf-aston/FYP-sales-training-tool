"use client";

import Link from "next/link";
import { buttonClass, Icon, Notice, Tabs } from "@/components/ui";
import { ProspectSetup } from "@/features/prospect/ProspectSetup";
import { useSession } from "@/features/session/SessionContext";
import { config } from "@/lib/config";
import { useUi } from "@/state/UiContext";
import { VoiceSettings } from "@/features/voice/VoiceSettings";
import { FlowControls } from "./FlowControls";
import { StatusCard } from "./StatusCard";
import { ToolsGrid } from "./ToolsGrid";
import s from "./Sidebar.module.css";

/** Role tab: on the buyer page, a door to the selling page; on the selling page, the buyer setup. */
function RoleTab() {
  const { role, prospect } = useSession();
  if (role === "seller") {
    return prospect ? <ProspectSetup /> : <Notice kind="empty">Set up your buyer in the main panel to start.</Notice>;
  }
  return (
    <div className={s.stack}>
      <div className={s.heading}>
        <h2>Want to sell instead?</h2>
        <p>Swap seats: the AI plays the buyer, you pick who they are and what they object to.</p>
      </div>
      <Link href={config.routes.sell} className={buttonClass("primary", s.switchLink)}>
        <Icon name="swap" size={16} /> Switch to selling
      </Link>
    </div>
  );
}

export function Sidebar() {
  const { sidebarTab, setSidebarTab } = useUi();
  const { role } = useSession();
  return (
    <aside id={config.ids.panels} className={s.sidebar} aria-label="Session sidebar" tabIndex={-1}>
      <StatusCard />
      <div className={s.tabs}>
        <Tabs
          label="Workspace"
          active={role === "seller" && sidebarTab === "session" ? "mode" : sidebarTab}
          onChange={setSidebarTab}
          tabs={[
            ...(role === "buyer" ? [{ key: "session" as const, label: "Session", content: <FlowControls /> }] : []),
            { key: "mode", label: role === "seller" ? "Setup" : "Role", content: <RoleTab /> },
            { key: "tools", label: "Tools", content: <ToolsGrid /> },
            { key: "settings", label: "Settings", content: <VoiceSettings /> },
          ]}
        />
      </div>
    </aside>
  );
}
