"use client";

import { useEffect, useState } from "react";
import { prospectConfig } from "./prospectConfig";

export interface Delta {
  n: number;
  key: number;
}

/** Returns the latest change in `pct` for a moment, then null, so a chip can float it. */
export function useReadinessDelta(pct: number): Delta | null {
  const [prev, setPrev] = useState(pct);
  const [delta, setDelta] = useState<Delta | null>(null);

  if (pct !== prev) {
    setPrev(pct);
    setDelta({ n: pct - prev, key: (delta?.key ?? 0) + 1 });
  }

  useEffect(() => {
    if (!delta) return;
    const t = setTimeout(() => setDelta(null), prospectConfig.deltaChipMs);
    return () => clearTimeout(t);
  }, [delta]);

  return delta;
}
