"use client";

// 404: say what happened, offer the three ways in, and go home on a countdown the learner can pause.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { AmbientFilm } from "@/components/film/AmbientFilm";
import { Button, Card, Eyebrow, buttonClass } from "@/components/ui";
import { config } from "@/lib/config";
import s from "./NotFound.module.css";

const TOTAL = config.notFound.redirectSeconds;
const { home, buy, sell } = config.routes;
const noSubscribe = () => () => {};

export function NotFound() {
  const router = useRouter();
  const [left, setLeft] = useState<number>(TOTAL);
  const [paused, setPaused] = useState(false);
  // Empty on the server: the page is prerendered once and served for every missing address.
  const path = useSyncExternalStore(noSubscribe, () => window.location.pathname, () => "");

  useEffect(() => {
    if (paused) return;
    if (left <= 0) return router.replace(home);
    const tick = setTimeout(() => setLeft((n) => n - 1), 1000);
    return () => clearTimeout(tick);
  }, [left, paused, router]);

  // Esc pauses, like the button.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setPaused(true);
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const toggle = () => {
    if (paused) setLeft(TOTAL);
    setPaused(!paused);
  };

  return (
    <>
      <AmbientFilm />
      <main className={s.page}>
        <Card className={s.card}>
          <Eyebrow>404</Eyebrow>
          <h1 className={s.title}>This page doesn&apos;t exist</h1>
          <p className={s.body}>
            {path ? <>Nothing lives at <code className={s.path}>{path}</code>.</> : "The link may be old or mistyped."}
          </p>

          <nav className={s.actions} aria-label="Where to go">
            <Link href={home} className={buttonClass("primary")}>Go home now</Link>
            <Link href={buy} className={buttonClass("secondary")}>Practise buying</Link>
            <Link href={sell} className={buttonClass("secondary")}>Practise selling</Link>
          </nav>

          {/* The bar drains in CSS over the full time; it unmounts while paused, so a restart starts it full. */}
          {!paused && (
            <div className={s.track} aria-hidden="true">
              <span className={s.fill} style={{ animationDuration: `${TOTAL}s` }} />
            </div>
          )}
          <div className={s.timerRow}>
            {/* Read once, not every second: a ticking live region is noise for screen readers. */}
            <p className={s.timer}>
              {paused ? "Paused. Stay as long as you like." : (
                <>Going home in <span aria-hidden="true">{left}</span><span className="sr-only">{TOTAL}</span> seconds</>
              )}
            </p>
            <Button variant="ghost" onClick={toggle} aria-keyshortcuts={paused ? undefined : "Escape"}>
              {paused ? "Restart timer" : "Stay here"}
            </Button>
          </div>
        </Card>
      </main>
    </>
  );
}
