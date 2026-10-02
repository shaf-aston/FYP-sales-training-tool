import type { HTMLAttributes } from "react";
import s from "./Card.module.css";

type Tone = "plain" | "accent" | "success" | "warning" | "danger";

interface Props extends HTMLAttributes<HTMLElement> {
  tone?: Tone;
  as?: "section" | "div" | "article" | "li";
}

/** A separated surface. Use only where an element must read as its own object. */
export function Card({ tone = "plain", as: Tag = "section", className, ...rest }: Props) {
  return <Tag {...rest} className={[s.card, s[tone], className].filter(Boolean).join(" ")} />;
}

export function Eyebrow({ children }: { children: React.ReactNode }) {
  return <p className={s.eyebrow}>{children}</p>;
}
