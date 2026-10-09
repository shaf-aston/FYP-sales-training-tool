"use client";

import { useCallback, useEffect, useState } from "react";
import { prefersReducedMotion } from "@/lib/motion";

/** Tracks which section is in view and scrolls to one (instantly under reduced motion). */
export function useScrollSpy(ids: string[], enabled: boolean) {
  const [active, setActive] = useState(ids[0]);
  const key = ids.join("|");

  useEffect(() => {
    if (!enabled) return;
    const els = key
      .split("|")
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => !!el);
    const io = new IntersectionObserver(
      (entries) => {
        const hit = entries.find((e) => e.isIntersecting);
        if (hit) setActive(hit.target.id);
      },
      { rootMargin: "-25% 0px -60% 0px" },
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [key, enabled]);

  const scrollTo = useCallback((id: string) => {
    const reduce = prefersReducedMotion();
    document.getElementById(id)?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    setActive(id);
  }, []);

  return { active, scrollTo };
}
