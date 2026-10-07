import type { Metadata } from "next";
import { KnowledgePage } from "@/features/knowledge/KnowledgePage";

export const metadata: Metadata = { title: "Knowledge base · Eloquence" };

export default function Page() {
  return <KnowledgePage />;
}
