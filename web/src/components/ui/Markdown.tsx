"use client";

import DOMPurify from "dompurify";
import { marked } from "marked";
import { useMemo } from "react";

// The only formatting model and transcript text may carry: emphasis, lists, code, the tone marks (<mark>). No links,
// images, forms or attributes: a buyer line from a pasted call (or a model talked into it) rendered a live link, a
// password form and a full-screen overlay, and loaded an outside image (live audit, 12 Nov). A tag left out keeps
// its text, so "[click here](...)" reads "click here".
const SAFE = {
  ALLOWED_TAGS: ["p", "br", "strong", "em", "b", "i", "ul", "ol", "li", "code", "pre", "blockquote", "mark"],
  ALLOWED_ATTR: [] as string[],
};

/** Renders model text as markdown. Output always goes through DOMPurify, kept to plain formatting. */
export function Markdown({ text, inline = false, className }: { text: string; inline?: boolean; className?: string }) {
  const html = useMemo(() => {
    const raw = inline ? marked.parseInline(text, { async: false }) : marked.parse(text, { async: false });
    return DOMPurify.sanitize(raw, SAFE);
  }, [text, inline]);
  const Tag = inline ? "span" : "div";
  return <Tag className={className} dangerouslySetInnerHTML={{ __html: html }} />;
}
