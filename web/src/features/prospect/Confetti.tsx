"use client";

import { useEffect, useRef } from "react";
import { config } from "@/lib/config";
import s from "./Confetti.module.css";

/** A short gold burst over its parent. Decorative; skipped when the user prefers reduced motion. */
export function Confetti() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const { count, durationMs, gravity } = config.prospect.confetti;
    const css = getComputedStyle(document.documentElement);
    const colours = ["--accent", "--accent-strong", "--warning"].map((v) => css.getPropertyValue(v).trim());
    const { width, height } = canvas.getBoundingClientRect();
    canvas.width = width;
    canvas.height = height;

    const bits = Array.from({ length: count }, (_, i) => ({
      x: width / 2,
      y: height * 0.25,
      vx: (Math.random() - 0.5) * 12,
      vy: -Math.random() * 9 - 2,
      size: 4 + Math.random() * 5,
      colour: colours[i % colours.length],
    }));

    const start = performance.now();
    let raf = 0;
    const frame = (now: number) => {
      const t = (now - start) / durationMs;
      ctx.clearRect(0, 0, width, height);
      if (t >= 1) return;
      ctx.globalAlpha = Math.max(0, 1 - t);
      for (const b of bits) {
        b.vy += gravity;
        b.x += b.vx;
        b.y += b.vy;
        ctx.fillStyle = b.colour;
        ctx.fillRect(b.x, b.y, b.size, b.size * 0.6);
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);
    return () => cancelAnimationFrame(raf);
  }, []);

  return <canvas ref={ref} className={s.canvas} aria-hidden="true" />;
}
