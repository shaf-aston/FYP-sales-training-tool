"use client";

import { useId, useRef } from "react";
import { Badge } from "@/components/ui";
import type { CallObjection } from "@/lib/api/types";
import { config } from "@/lib/config";
import s from "./ObjectionList.module.css";

/** The prospect's objections in their own words, each with its kind; the learner can drop any. */
export function ObjectionList({ items, onChange }: { items: CallObjection[]; onChange: (items: CallObjection[]) => void }) {
  const id = useId();
  const group = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLUListElement>(null);

  // The × goes with its row: move keyboard focus to the next row's × (or the group when none are left).
  const remove = (i: number) => {
    onChange(items.filter((_, j) => j !== i));
    requestAnimationFrame(() => {
      const buttons = list.current?.querySelectorAll("button");
      (buttons?.length ? buttons[Math.min(i, buttons.length - 1)] : group.current)?.focus();
    });
  };

  return (
    <div ref={group} className={s.field} role="group" aria-labelledby={id} tabIndex={-1}>
      <span id={id} className={s.label}>
        Objections
      </span>
      {items.length ? (
        <ul ref={list} className={s.list}>
          {items.map((o, i) => (
            <li key={`${o.type}:${o.text}`} className={s.item}>
              <Badge tone="warning">{config.calls.objectionTypes[o.type]}</Badge>
              <q className={s.quote}>{o.text}</q>
              <button type="button" className={s.remove} aria-label={`Remove objection: ${o.text}`} onClick={() => remove(i)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={s.empty}>None raised on the call.</p>
      )}
    </div>
  );
}
