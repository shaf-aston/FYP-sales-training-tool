"use client";

// 404: say what happened, offer the three ways in, and go home on a countdown the learner can stop.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, useSyncExternalStore } from "react";
import { AmbientFilm } from "@/components/film/AmbientFilm";
import { Button, Card, Eyebrow, buttonClass } from "@/components/ui";
import { config } from "@/lib/config";
import s from "./NotFound.module.css";

const TOTAL = config.notFound.redirectSeconds;
const noSubscribe = () => () => {};

export function NotFound() {
  const router = useRouter();
  const [left, setLeft] = useState<number>(TOTAL);
  const [staying, setStaying] = useState(false);
  // Empty on the server: the page is prerendered once and served for every missing address.
  const path = useSyncExternalStore(noSubscribe, () => window.location.pathname, () => "");

  useEffect(() => {
    if (staying) return;
    if (left <= 0) {
      router.replace(config.routes.home);
      return;
    }
    const tick = setTimeout(() => setLeft((n) => n - 1), 1000);
    return () => clearTimeout(tick);
  }, [left, staying, router]);

  return (
    <>
      <AmbientFilm />
      <main className={s.page}>
        <Card className={s.card}>
          <Eyebrow>404</Eyebrow>
          <h1 className={s.title}>This page doesn&apos;t exist</h1>
          <p className={s.body}>
            {path ? (
              <>
                Nothing lives at <code className={s.path}>{path}</code>.
              </>
            ) : (
              "The link may be old or mistyped."
            )}
          </p>

          <div className={s.actions}>
            <Link href={config.routes.home} className={buttonClass("primary")}>
              Go home now
            </Link>
            <Link href={config.routes.buy} className={buttonClass("secondary")}>
              Practise buying
            </Link>
            <Link href={config.routes.sell} className={buttonClass("secondary")}>
              Practise selling
            </Link>
          </div>

          {staying ? (
            <p className={s.timer}>You&apos;re staying here.</p>
          ) : (
            <div className={s.countdown}>
              <div className={s.track} aria-hidden="true">
                <span className={s.fill} style={{ width: `${(left / TOTAL) * 100}%` }} />
              </div>
              <div className={s.timerRow}>
                {/* Announced once, not every second: a ticking live region is noise for screen readers. */}
                <p className={s.timer}>
                  Going home in <span aria-hidden="true">{left}</span>
                  <span className={s.srOnly}>{TOTAL}</span> seconds
                </p>
                <Button variant="ghost" onClick={() => setStaying(true)}>
                  Stay here
                </Button>
              </div>
            </div>
          )}
        </Card>
      </main>
    </>
  );
}
