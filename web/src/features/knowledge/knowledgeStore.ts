// This browser's copy of the learner's product details. Every new sell call sends it (SessionContext), so the buyer
// reads this learner's details and nobody else's. Signed in, the account holds the same copy (useKnowledge).

import { storageKeys } from "@/lib/config";
import { readString, writeString } from "@/lib/storage";
import type { KnowledgeData } from "@/lib/api/types";

export function readLocalKnowledge(): KnowledgeData {
  try {
    const data = JSON.parse(readString(storageKeys.knowledge) ?? "{}");
    return data && typeof data === "object" && !Array.isArray(data) ? (data as KnowledgeData) : {};
  } catch {
    return {};
  }
}

/** Null or an empty object forgets it. */
export function writeLocalKnowledge(data: KnowledgeData | null): void {
  writeString(storageKeys.knowledge, data && Object.keys(data).length ? JSON.stringify(data) : null);
}
