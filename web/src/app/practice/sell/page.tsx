import type { Metadata } from "next";
import { AppShell } from "@/features/shell/AppShell";

export const metadata: Metadata = { title: "Be the seller · Eloquence" };

export default function Sell() {
  return <AppShell role="seller" />;
}
