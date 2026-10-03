"use client";

// Night-city film: blurred city lights drifting behind the app. Drawn live, so it
// loads nothing and never shows people. Colours and count come from tokens.css.

import { useEffect, useRef } from "react";
import { config } from "@/lib/config";
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

export function AmbientFilm() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const film = config.film;
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const hues = token("--film-hues").split(/\s+/).map(Number);
    const count = Number(token("--film-light-count")) || 0;
    const skyTop = token("--film-sky-top");
    const skyBottom = token("--film-sky-bottom");
    const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

    const lights: Light[] = Array.from({ length: count }, () => ({
      x: Math.random(),
      y: film.yMin + Math.random() * (1 - film.yMin),
      r: film.radius.min + Math.random() * film.radius.span,
      speed: film.speed.min + Math.random() * film.speed.span,
      hue: hues[Math.floor(Math.random() * hues.length)],
      alpha: film.alpha.min + Math.random() * film.alpha.span,
      phase: Math.random() * film.phaseSpan,
    }));

    const resize = () => {
      const dpr = Math.min(devicePixelRatio || 1, film.maxDpr);
      canvas.width = innerWidth * dpr;
      canvas.height = innerHeight * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    let last = 0;
    const draw = (t: number) => {
      // Capped so lights do not jump after the tab was hidden.
      const steps = last ? Math.min((t - last) / film.baseFrameMs, film.frameMs / film.baseFrameMs * 2) : 0;
      last = t;
      const w = innerWidth;
      const h = innerHeight;
      const sky = ctx.createLinearGradient(0, 0, 0, h);
      sky.addColorStop(0, skyTop);
      sky.addColorStop(1, skyBottom);
      ctx.fillStyle = sky;
      ctx.fillRect(0, 0, w, h);
      for (const l of lights) {
        if (!still) l.x = (l.x + l.speed * steps) % film.wrapAt;
        const x = l.x * w;
        const y = l.y * h;
        const a = l.alpha * (film.flickerBase + film.flickerDepth * Math.sin(t / film.flickerMs + l.phase));
        const g = ctx.createRadialGradient(x, y, 0, x, y, l.r);
        g.addColorStop(0, `hsla(${l.hue}, ${film.lightness}, ${a})`);
        g.addColorStop(1, `hsla(${l.hue}, ${film.lightness}, 0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(x, y, l.r, 0, Math.PI * 2);
        ctx.fill();
      }
    };

    let frame = 0;
    const loop = (t: number) => {
      if (!document.hidden && t - last >= film.frameMs) draw(t);
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
