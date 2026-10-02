"use client";

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

/** Renders model text as markdown. Output always goes through DOMPurify. */
export function Markdown({ text, inline = false, className }: { text: string; inline?: boolean; className?: string }) {
  const html = useMemo(() => {
    const raw = inline ? marked.parseInline(text, { async: false }) : marked.parse(text, { async: false });
    return DOMPurify.sanitize(raw);
  }, [text, inline]);
  const Tag = inline ? "span" : "div";
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
