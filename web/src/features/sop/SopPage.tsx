"use client";

import Link from "next/link";
import { AmbientFilm } from "@/components/film/AmbientFilm";
import { Card, ToastProvider } from "@/components/ui";
import { config } from "@/lib/config";
import { CallCheck } from "./CallCheck";
import { SopResult } from "./SopResult";
import { SopSource } from "./SopSource";
import { useSopReader } from "./useSopReader";
import s from "./Sop.module.css";

function Review() {
  const reader = useSopReader();
  const { result } = reader;
  return (
    <>
      <Card className={s.card} aria-labelledby="sop-step-1">
        <h2 id="sop-step-1" className={s.cardTitle}>
          <span className={s.num}>1</span> Your SOP
        </h2>
        {result ? <SopResult result={result} source={reader.source} onBack={reader.back} /> : <SopSource reader={reader} />}
      </Card>
      {result && (
        <Card className={s.card} aria-labelledby="sop-step-2">
          <h2 id="sop-step-2" className={s.cardTitle}>
            <span className={s.num}>2</span> Check a call against it
          </h2>
          <CallCheck key={reader.version} stages={result.stages} />
        </Card>
      )}
    </>
  );
}

/** SOP review: read a team's sales SOP, see what of a good call it covers, then check a real call against it. */
export function SopPage() {
  return (
    <ToastProvider>
      <AmbientFilm />
      <main className={s.page}>
        <header className={s.header}>
          <div className={s.intro}>
            <h1 className={s.title}>SOP review</h1>
            <p className={s.muted}>See what your sales SOP covers, then how a real call follows it.</p>
          </div>
          <Link href={config.routes.sell} className={s.back}>
            ← Back to selling
          </Link>
        </header>
        <Review />
      </main>
    </ToastProvider>
  );
}
