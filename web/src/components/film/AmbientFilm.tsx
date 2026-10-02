"use client";

// Night-city film: blurred city lights drifting behind the app. Drawn live, so it
// loads nothing and never shows people. Colours and count come from tokens.css.

import { useEffect, useRef } from "react";
import s from "./AmbientFilm.module.css";

interface Light {
  x: number;
  y: number;
  r: number;
  speed: number;
  hue: number;
  alpha: number;
  phase: number;
}

const MAX_DPR = 2;

export function AmbientFilm() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const hues = token("--film-hues").split(/\s+/).map(Number);
    const count = Number(token("--film-light-count")) || 0;
    const skyTop = token("--film-sky-top");
    const skyBottom = token("--film-sky-bottom");
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

    const lights: Light[] = Array.from({ length: count }, () => ({
      x: Math.random(),
      y: 0.3 + Math.random() * 0.7,
      r: 10 + Math.random() * 40,
      speed: 0.00015 + Math.random() * 0.0007,
      hue: hues[Math.floor(Math.random() * hues.length)],
      alpha: 0.1 + Math.random() * 0.22,
      phase: Math.random() * 6,
    }));

    const resize = () => {
      const dpr = Math.min(devicePixelRatio || 1, MAX_DPR);
      canvas.width = innerWidth * dpr;
      canvas.height = innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (t: number) => {
      const w = innerWidth;
      const h = innerHeight;
      const sky = ctx.createLinearGradient(0, 0, 0, h);
      sky.addColorStop(0, skyTop);
      sky.addColorStop(1, skyBottom);
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, h);
      for (const l of lights) {
        if (!still) l.x = (l.x + l.speed) % 1.1;
        const x = l.x * w;
        const y = l.y * h;
        const a = l.alpha * (0.7 + 0.3 * Math.sin(t / 700 + l.phase));
        const g = ctx.createRadialGradient(x, y, 0, x, y, l.r);
        g.addColorStop(0, `hsla(${l.hue}, 90%, 65%, ${a})`);
        g.addColorStop(1, `hsla(${l.hue}, 90%, 65%, 0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, l.r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    let frame = 0;
    const loop = (t: number) => {
      if (!document.hidden) draw(t);
      frame = requestAnimationFrame(loop);
    };
    const onResize = () => {
      resize();
      draw(performance.now());
    };

    resize();
    draw(0);
    if (!still) frame = requestAnimationFrame(loop);
    addEventListener("resize", onResize);
    return () => {
      cancelAnimationFrame(frame);
      removeEventListener("resize", onResize);
    };
  }, []);

  return <canvas ref={ref} className={s.film} aria-hidden="true" />;
}
