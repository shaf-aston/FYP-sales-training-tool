import type { Metadata } from "next";
import { AppShell } from "@/features/shell/AppShell";

export const metadata: Metadata = { title: "Buy · Eloquence" };

/** Buy mode: the learner is the customer and the AI seller sells to them. */
export default function Buy() {
  return <AppShell mode="buy" />;
}
