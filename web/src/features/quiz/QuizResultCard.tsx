"use client";

import { Card, Eyebrow, Markdown } from "@/components/ui";
import type { QuizResult } from "@/lib/api/types";
import { stageMeta, strategyMeta } from "@/lib/labels";
import { scoreBand, scorePercent, type QuizKind } from "./scoring";
import { useCountUp } from "@/lib/useCountUp";
import s from "./quiz.module.css";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className={s.block}>
      <Eyebrow>{title}</Eyebrow>
      {children}
    </div>
  );
}

function List({ title, items }: { title: string; items?: string[] }) {
  if (!items?.length) return null;
  return (
    <Block title={title}>
      <ul className={s.list}>
        {items.map((t, i) => (
          <li key={i}>
            <Markdown inline text={t} />
          </li>
        ))}
      </ul>
    </Block>
  );
}

export function QuizResultCard({ result, kind }: { result: QuizResult; kind: QuizKind }) {
  const percent = scorePercent(kind, result.score);
  const shown = useCountUp(percent);
  const band = scoreBand(kind, percent);
  const label = percent === null ? "Unavailable" : `${shown}%`;
  const exp = result.expected;

  return (
    <Card tone={band} className={s.result} aria-live="polite">
      <div className={s.head}>
        <span className={s.score}>{label}</span>
      </div>
      {result.feedback && <Markdown className={s.body} text={result.feedback} />}
      <List title="Strengths" items={result.strengths} />
      <List title="Improvements" items={result.improvements} />
      {result.before?.length ? (
        <Block title="What you said first">
          <ul className={`${s.list} ${s.signed}`}>
            {result.before.map((b, i) => (
              <li key={i} className={b.good ? s.good : s.bad}>
                {b.good ? "+ " : "- "}
                <Markdown inline text={b.text} />
              </li>
            ))}
          </ul>
        </Block>
      ) : null}
      <List title="Concepts you got" items={result.key_concepts_got} />
      <List title="Concepts to review" items={result.key_concepts_missed} />
      {result.coach_tip && (
        <Block title="Coach tip">
          <Markdown className={s.body} text={result.coach_tip} />
        </Block>
      )}
      {exp && (
        <Block title="Expected">
          <p className={s.body}>
            {stageMeta(exp.stage).label} ({strategyMeta(exp.strategy).label} approach)
          </p>
        </Block>
      )}
    </Card>
  );
}
