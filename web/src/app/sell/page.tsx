import type { Metadata } from "next";
import { AppShell } from "@/features/shell/AppShell";

export const metadata: Metadata = { title: "Sell · Eloquence" };

/** Sell mode: the learner is the salesperson and the AI buyer answers. */
export default function Sell() {
  return <AppShell mode="sell" />;
}
