"use client";

import { useEffect, useState } from "react";
import { config } from "./config";
import { prefersReducedMotion } from "@/lib/motion";

/** Counts 0 -> target with an ease-out; jumps straight there under reduced motion. `null` holds at 0. */
export function useCountUp(target: number | null, ms: number = config.countUpMs): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    if (target === null) return;
    const reduced = prefersReducedMotion();
    const start = performance.now();
    let raf = 0;
    const tick = (now: number) => {
      const t = reduced || ms <= 0 ? 1 : Math.min(1, (now - start) / ms);
      setValue(Math.round(target * (1 - (1 - t) ** 3)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return value;
}
