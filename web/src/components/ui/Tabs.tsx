"use client";

import { useId, useRef, type KeyboardEvent, type ReactNode } from "react";
import s from "./Tabs.module.css";

interface Tab<K extends string> {
  key: K;
  label: string;
  content: ReactNode;
}

interface Props<K extends string> {
  label: string;
  tabs: Tab<K>[];
  active: K;
  onChange: (key: K) => void;
}

/** WAI-ARIA tabs: arrow keys wrap, Home/End jump, only the active tab is in the tab order. */
export function Tabs<K extends string>({ label, tabs, active, onChange }: Props<K>) {
  const id = useId();
  const list = useRef<HTMLDivElement>(null);

  const onKey = (e: KeyboardEvent) => {
    const i = tabs.findIndex((t) => t.key === active);
    const moves: Record<string, number> = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 };
    const next = moves[e.key];
    if (next === undefined) return;
    e.preventDefault();
    const tab = tabs[(next + tabs.length) % tabs.length];
    onChange(tab.key);
    list.current?.querySelector<HTMLButtonElement>(`[data-key="${tab.key}"]`)?.focus();
  };

  return (
    <div className={s.wrap}>
      <div ref={list} role="tablist" aria-label={label} className={s.list} onKeyDown={onKey}>
        {tabs.map((t) => (
          <button
            key={t.key}
            type="button"
            role="tab"
            data-key={t.key}
            id={`${id}-${t.key}-tab`}
            aria-controls={`${id}-${t.key}`}
            aria-selected={t.key === active}
            tabIndex={t.key === active ? 0 : -1}
            className={s.tab}
            onClick={() => onChange(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tabs.map((t) => (
        <div
          key={t.key}
          role="tabpanel"
          id={`${id}-${t.key}`}
          aria-labelledby={`${id}-${t.key}-tab`}
          hidden={t.key !== active}
          className={s.panel}
        >
          {t.key === active && t.content}
        </div>
      ))}
    </div>
  );
}
