import type { Metadata } from "next";
import { NotFound } from "@/features/not-found/NotFound";

export const metadata: Metadata = { title: "Page not found · Eloquence" };

export default function Page() {
  return <NotFound />;
}
