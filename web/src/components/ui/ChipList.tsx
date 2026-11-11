"use client";

import { useId, useRef, useState, type ReactNode } from "react";
import { Button } from "./Button";
import f from "./Field.module.css";
import s from "./ChipList.module.css";

interface Props {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  /** What one item is called, for the add box and screen readers: "need" → "Add a need". */
  noun: string;
  maxLength?: number;
  maxItems?: number;
  /** Shown under the chips, above the add box, e.g. where the items came from. */
  hint?: ReactNode;
}

/** An editable list of short items: remove one with ×, add one with Enter or the Add button. Duplicates are ignored. */
export function ChipList({ label, items, onChange, noun, maxLength, maxItems = Infinity, hint }: Props) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [draft, setDraft] = useState("");
  const full = items.length >= maxItems;

  const add = () => {
    const item = draft.trim();
    if (!item || full) return;
    if (!items.some((x) => x.toLowerCase() === item.toLowerCase())) onChange([...items, item]);
    setDraft("");
  };

  // The × button disappears with its chip, so keep keyboard focus in the list.
  const remove = (i: number) => {
    onChange(items.filter((_, j) => j !== i));
    input.current?.focus();
  };

  return (
    <div className={f.field} role="group" aria-labelledby={`${id}-label`}>
      <span id={`${id}-label`} className={f.label}>
        {label}
      </span>
      {items.length ? (
        <ul className={s.chips}>
          {items.map((item, i) => (
            <li key={item} className={s.chip}>
              <span className={s.text}>{item}</span>
              <button type="button" className={s.remove} aria-label={`Remove ${noun}: ${item}`} onClick={() => remove(i)}>
                ×
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className={s.empty}>None yet.</p>
      )}
      {hint && <div className={f.meta}>{hint}</div>}
      {!full && (
        <div className={s.add}>
          <label htmlFor={id} className="sr-only">
            Add a {noun}
          </label>
          <input
            ref={input}
            id={id}
            className={f.control}
            value={draft}
            maxLength={maxLength}
            placeholder={`Add a ${noun}`}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key !== "Enter") return;
              e.preventDefault();
              add();
            }}
          />
          <Button onClick={add} disabled={!draft.trim()}>
            Add
          </Button>
        </div>
      )}
    </div>
  );
}
