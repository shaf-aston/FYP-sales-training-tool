import { config } from "@/lib/config";
import type { KnowledgeData, KnowledgeField } from "@/lib/api/types";

interface FieldDef {
  id: KnowledgeField;
  label: string;
  title: string;
  hint: string;
  placeholder: string;
  max: number;
  multiline: boolean;
}

const LONG = config.knowledge.fieldMax;
const SHORT_SECTION_CHARS = 10;

export const FIELDS: FieldDef[] = [
  { id: "product_name", label: "Product", title: "Product or service name", hint: "What the buyer should hear you call the product.", max: config.knowledge.nameMax, multiline: false, placeholder: "e.g., BMW 5 Series, Pro CRM Plan, Dark Oud Fragrance" },
  { id: "pricing", label: "Pricing", title: "Pricing details", hint: "Add exact prices, tiers, discounts, and packaging.", max: LONG, multiline: true, placeholder: "e.g., Starter: $29/user/mo, Pro: $79/user/mo" },
  { id: "specifications", label: "Features", title: "Key features or specifications", hint: "Highlight the details that matter in real sales conversations.", max: LONG, multiline: true, placeholder: "e.g., API access, unlimited storage, SSO" },
  { id: "company_info", label: "Company", title: "Company background", hint: "Anything about your company that strengthens credibility.", max: LONG, multiline: true, placeholder: "e.g., Founded 2018, 500+ clients served" },
  { id: "selling_points", label: "Value", title: "Best selling points", hint: "What makes this stand out against competitors?", max: LONG, multiline: true, placeholder: "e.g., Best resale value in class, 10-year warranty" },
  { id: "additional_notes", label: "Notes", title: "Buyer notes and objections", hint: "Capture common objections, audiences, offers, and context.", max: LONG, multiline: true, placeholder: "e.g., Common objection: 'too expensive' - counter with ROI" },
];

export type Values = Record<KnowledgeField, string>;

export const emptyValues = (): Values => Object.fromEntries(FIELDS.map((f) => [f.id, ""])) as Values;

export const fromData = (data: KnowledgeData): Values => ({ ...emptyValues(), ...data });

/** Only the non-empty, trimmed fields: what the server stores. */
export function toPayload(values: Values): KnowledgeData {
  const out: KnowledgeData = {};
  for (const f of FIELDS) {
    const v = values[f.id].trim();
    if (v) out[f.id] = v;
  }
  return out;
}

/** Titles of filled sections (except the product name) that look too thin to help the buyer bot. */
export function shortSections(payload: KnowledgeData): string[] {
  return FIELDS.filter((f) => f.id !== "product_name" && payload[f.id] && payload[f.id]!.length < SHORT_SECTION_CHARS).map((f) => f.title);
}

/** A plain preview of the saved notes. The AI buyer gets its own labelled version (core/knowledge.py). */
export function briefText(payload: KnowledgeData): string {
  const lines = FIELDS.filter((f) => payload[f.id]).map((f) => `${f.id}: ${payload[f.id]}`);
  if (!lines.length) return "(no data entered)";
  return ["Custom product notes:", ...lines].join("\n");
}
