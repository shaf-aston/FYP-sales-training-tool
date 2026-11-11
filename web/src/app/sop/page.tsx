import type { Metadata } from "next";
import { SopPage } from "@/features/sop/SopPage";

export const metadata: Metadata = { title: "SOP review · Eloquence" };

/** SOP review: what a team's sales SOP covers, and how a real call follows it. */
export default function Page() {
  return <SopPage />;
}
