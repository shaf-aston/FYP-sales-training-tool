import type { Metadata } from "next";
import { KnowledgePage } from "@/features/knowledge/KnowledgePage";

export const metadata: Metadata = { title: "Product knowledge · Eloquence" };

export default function Page() {
  return <KnowledgePage />;
}
