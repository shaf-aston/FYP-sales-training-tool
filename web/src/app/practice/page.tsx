import type { Metadata } from "next";
import { AppShell } from "@/features/shell/AppShell";

export const metadata: Metadata = { title: "Practice · Eloquence" };

export default function Practice() {
  return <AppShell />;
}
