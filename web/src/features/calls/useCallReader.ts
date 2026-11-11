"use client";

// State for "From a real call": the transcript the learner brings, the server's reading of it,
// and the prospect they edit before practising. Every change happens in an event handler.

import { useRef, useState } from "react";
import { api, errorText } from "@/lib/api/client";
import type { CallProfile, CallReadRes, CallReq, CustomBuyer, Difficulty } from "@/lib/api/types";
import { config } from "@/lib/config";

/** The prospect as the learner edits it: the buyer to practise against, plus how hard they are. */
export interface ProspectDraft extends CustomBuyer {
  difficulty: Difficulty;
}

/** A read call and the exact request behind it (rep filled in), so the review reads the same call. */
export interface CallResult {
  call: CallReadRes;
  source: CallReq;
}

type Busy = "file" | "sample" | "read" | null;

const { accept, maxFileBytes } = config.calls;
/** ".txt, .vtt or .srt" */
const acceptList = `${accept.slice(0, -1).join(", ")} or ${accept[accept.length - 1]}`;

const unique = (items: string[]) => [...new Set(items.map((x) => x.trim()).filter(Boolean))];

function draftOf(p: CallProfile): ProspectDraft {
  return {
    name: p.name,
    background: p.background,
    personality: p.personality,
    budget: p.budget,
    needs: unique(p.needs),
    pain_points: unique(p.pain_points),
    objections: p.objections,
    difficulty: p.difficulty,
  };
}

/** What /api/sell/init takes as custom_buyer. */
export function toCustomBuyer(d: ProspectDraft): CustomBuyer {
  return {
    name: d.name.trim(),
    background: d.background.trim(),
    personality: d.personality.trim(),
    budget: d.budget.trim(),
    needs: d.needs,
    pain_points: d.pain_points,
    objections: d.objections,
  };
}

function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

export function useCallReader() {
  const [text, setText] = useState("");
  /** The uploaded file's name; it tells the server the format (.vtt, .srt). */
  const [filename, setFilename] = useState<string | undefined>();
  const [result, setResult] = useState<CallResult | null>(null);
  const [draft, setDraft] = useState<ProspectDraft | null>(null);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState("");
  /** Bumped by every new job (and by "back"), so a late answer from an old one is dropped. */
  const ticket = useRef(0);

  /** Runs one job with busy and error handling; resolves undefined when it failed or was replaced. */
  const run = async <R>(kind: Busy, job: () => Promise<R>, fallback: string): Promise<R | undefined> => {
    const my = ++ticket.current;
    setBusy(kind);
    setError("");
    try {
      const out = await job();
      return my === ticket.current ? out : undefined;
    } catch (err) {
      if (my === ticket.current) setError(errorText(err, fallback));
    } finally {
      if (my === ticket.current) setBusy(null);
    }
  };

  const read = async (call: CallReq) => {
    const res = await run("read", () => api.callsRead(call), "Couldn't read that call. Try again.");
    if (!res) return;
    setResult({ call: res, source: { ...call, rep: res.rep.name } });
    setDraft(draftOf(res.profile));
  };

  return {
    text,
    filename,
    result,
    draft,
    busy,
    error,
    /** Typing in the box; an emptied box forgets the file it came from. */
    setText: (t: string) => {
      setText(t);
      if (!t.trim()) setFilename(undefined);
    },
    loadFile: async (file: File) => {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      if (!(accept as readonly string[]).includes(ext)) return setError(`Use a ${acceptList} file.`);
      if (file.size > maxFileBytes) return setError("That file is too big for one call.");
      const t = await run("file", () => readText(file), "Couldn't open that file.");
      if (t === undefined) return;
      setText(t);
      setFilename(file.name);
    },
    /** Loads the sample transcript and reads it straight away. */
    loadSample: async () => {
      const res = await run("sample", api.callsSample, "Couldn't load the sample call.");
      if (!res) return;
      setText(res.text);
      setFilename(res.filename);
      await read({ text: res.text, filename: res.filename });
    },
    read: () => read({ text, filename }),
    /** "That's me": read the same call again with this speaker as the learner. Edits to the prospect start over. */
    pickRep: (rep: string) => result && read({ ...result.source, rep }),
    edit: (patch: Partial<ProspectDraft>) => setDraft((d) => d && { ...d, ...patch }),
    /** Back to the transcript box (the text stays). */
    back: () => {
      ticket.current++;
      setResult(null);
      setDraft(null);
      setBusy(null);
      setError("");
    },
    acceptList,
  };
}

export type CallReader = ReturnType<typeof useCallReader>;
