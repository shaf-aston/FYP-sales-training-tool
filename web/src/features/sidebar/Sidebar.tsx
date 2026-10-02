"use client";

import { Tabs } from "@/components/ui";
import { ProspectSetup } from "@/features/prospect/ProspectSetup";
import { useUi } from "@/features/shell/UiContext";
import { VoiceSettings } from "@/features/voice/VoiceSettings";
import { FlowControls } from "./FlowControls";
import { StatusCard } from "./StatusCard";
import { ToolsGrid } from "./ToolsGrid";
import s from "./Sidebar.module.css";

export function Sidebar() {
  const { sidebarTab, setSidebarTab } = useUi();
  return (
    <aside className={s.sidebar} aria-label="Session sidebar">
      <StatusCard />
      <div className={s.tabs}>
        <Tabs
          label="Workspace"
          active={sidebarTab}
          onChange={setSidebarTab}
          tabs={[
            { key: "session", label: "Session", content: <FlowControls /> },
            { key: "mode", label: "Mode", content: <ProspectSetup /> },
            { key: "tools", label: "Tools", content: <ToolsGrid /> },
            { key: "settings", label: "Settings", content: <VoiceSettings /> },
          ]}
        />
      </div>
    </aside>
  );
}
