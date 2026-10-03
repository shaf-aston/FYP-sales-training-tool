"use client";

import { config } from "@/lib/config";
import Link from "next/link";
import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { AmbientFilm } from "@/components/film/AmbientFilm";
import { Button, Card, ConfirmProvider, Eyebrow, Notice, TextArea, TextInput, ToastProvider } from "@/components/ui";
import { FIELDS } from "./fields";
import { useKnowledge } from "./useKnowledge";
import { useScrollSpy } from "./useScrollSpy";
import s from "./KnowledgePage.module.css";

const sectionId = (id: string) => `s-${id}`;
const SECTION_IDS = FIELDS.map((f) => sectionId(f.id));

function BackLink() {
  const prospect = useSearchParams().get("mode") === "prospect";
  return (
    <Link href={config.routes.practice} className={s.back}>
      ← {prospect ? "Back to prospect practice" : "Back to chat"}
    </Link>
  );
}

function Editor() {
  const k = useKnowledge();
  const { active, scrollTo } = useScrollSpy(SECTION_IDS, !k.loading && !k.loadError);

  if (k.loading) return <Notice kind="loading">Loading your saved details…</Notice>;
  if (k.loadError)
    return (
      <Notice
        kind="error"
        action={
          <Button onClick={k.reload}>
            Try again
          </Button>
        }
      >
        {k.loadError}
      </Notice>
    );

  return (
    <>
      <div className={s.body}>
        <nav className={s.nav} aria-label="Sections">
          {FIELDS.map((f) => (
            <a
              key={f.id}
              href={`#${sectionId(f.id)}`}
              className={`${s.navLink} ${active === sectionId(f.id) ? s.active : ""}`}
              aria-current={active === sectionId(f.id) ? "true" : undefined}
              onClick={(e) => {
                e.preventDefault();
                scrollTo(sectionId(f.id));
              }}
            >
              <span>{f.label}</span>
              <span className={`${s.dot} ${k.values[f.id].trim() ? s.dotOn : ""}`} role="img" aria-label={k.values[f.id].trim() ? "filled in" : "empty"} />
            </a>
          ))}
        </nav>
        <div className={s.fields}>
          <Card tone="accent" className={s.note}>
            These notes are added to the chatbot&apos;s session prompt as custom product data. Focus on details unique to your scenario. Changes apply after you reset the chat session.
          </Card>
          {FIELDS.map((f) => {
            const common = {
              label: f.title,
              hint: f.hint,
              placeholder: f.placeholder,
              maxLength: f.max,
              value: k.values[f.id],
            };
            return (
              <Card key={f.id} id={sectionId(f.id)} className={s.field}>
                {f.multiline ? (
                  <TextArea {...common} rows={4} count={k.values[f.id].length} onChange={(e) => k.setField(f.id, e.target.value)} />
                ) : (
                  <TextInput {...common} onChange={(e) => k.setField(f.id, e.target.value)} />
                )}
              </Card>
            );
          })}
        </div>
      </div>
      <details className={s.preview}>
        <summary>Preview the product brief the assistant will read</summary>
        <pre>{k.brief}</pre>
      </details>
      <div className={s.actions}>
        <Button variant="primary" busy={k.busy === "save"} busyLabel="Saving…" disabled={k.busy !== null} onClick={k.save}>
          Save details
        </Button>
        <Button variant="danger" busy={k.busy === "clear"} busyLabel="Clearing…" disabled={k.busy !== null} onClick={k.clearAll}>
          Clear all
        </Button>
      </div>
    </>
  );
}

export function KnowledgePage() {
  return (
    <ToastProvider>
      <ConfirmProvider>
        <AmbientFilm />
        <main className={s.page}>
          <header className={s.header}>
            <div>
              <Eyebrow>Knowledge workspace</Eyebrow>
              <h1 className={s.title}>Product Knowledge</h1>
              <p className={s.subtitle}>Add the details that make your practice scenario feel real. Keep it specific to your product or offer.</p>
            </div>
            <Suspense fallback={<Link href={config.routes.practice} className={s.back}>← Back to chat</Link>}>
              <BackLink />
            </Suspense>
          </header>
          <Editor />
        </main>
      </ConfirmProvider>
    </ToastProvider>
  );
}
