"use client";

// State for "From a real call": the transcript the learner brings, the server's reading of it,
// and the prospect they edit before practising. Every change happens in an event handler.

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { CallProfile, CallReadRes, CallReq, CustomBuyer, Difficulty } from "@/lib/api/types";
import { config } from "@/lib/config";
import { hasExt, listOf, megabytes, readText } from "@/lib/files";
import { useJob } from "@/lib/useJob";

/** The prospect as the learner edits it: the buyer to practise against, plus how hard they are. */
export interface ProspectDraft extends CustomBuyer {
  difficulty: Difficulty;
}

/** A read call and the exact request behind it (rep filled in), so the review reads the same call. */
export interface CallResult {
  call: CallReadRes;
  source: CallReq;
}

/** "audio": a recording is being turned into text (the slow one: about a minute per hour of audio). */
type Busy = "file" | "audio" | "sample" | "read";
/** Who labelled the speakers: the transcript itself (false), or AI from a recording ("unsure": check the labels). */
export type AiLabels = false | "sure" | "unsure";

const { accept, maxFileBytes, audio } = config.calls;
/** Everything the drop zone takes: transcripts and recordings. */
const acceptAll = [...accept, ...audio.accept];

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

export function useCallReader() {
  const [text, setText] = useState("");
  /** The uploaded file's name; it tells the server the format (.vtt, .srt). */
  const [filename, setFilename] = useState<string | undefined>();
  const [result, setResult] = useState<CallResult | null>(null);
  const [draft, setDraft] = useState<ProspectDraft | null>(null);
  const { busy, error, setError, run, cancel } = useJob<Busy>();
  /** From a recording, its speakers were labelled by AI: "sure", or "unsure" when most labels came back unreadable. */
  const [aiLabelled, setAiLabelled] = useState<AiLabels>(false);
  const read = async (call: CallReq) => {
    const res = await run("read", () => api.callsRead(call), "Couldn't read that call. Try again.");
    if (!res) return;
    setResult({ call: res, source: { ...call, rep: res.rep.name } });
    setDraft(draftOf(res.profile));
  };

  /** Put a transcript in the box (and remember where it came from), then read it at once. */
  const load = async (t: string, name: string, fromRecording: AiLabels) => {
    setText(t);
    setFilename(name);
    setAiLabelled(fromRecording);
    await read({ text: t, filename: name });
  };

  return {
    text,
    filename,
    result,
    draft,
    busy,
    error,
    aiLabelled,
    /** Typing in the box; an emptied box forgets the file it came from. */
    setText: (t: string) => {
      setText(t);
      if (t.trim()) return;
      setFilename(undefined);
      setAiLabelled(false);
    },
    /** A transcript goes in the box to check; a recording is turned into text on the server and read at once. */
    loadFile: async (file: File) => {
      if (hasExt(file, audio.accept)) {
        if (file.size > audio.maxBytes) return setError(`That recording is over ${megabytes(audio.maxBytes)}. Export the call's transcript instead.`);
        const res = await run("audio", () => api.callsTranscribe(file), "Couldn't turn that recording into text. Try again.");
        if (res) await load(res.text, res.filename, res.labels_sure ? "sure" : "unsure");
        return;
      }
      if (!hasExt(file, accept)) return setError(`Use a transcript (${listOf(accept)}) or a call recording.`);
      if (file.size > maxFileBytes) return setError("That file is too big for one call.");
      const t = await run("file", () => readText(file), "Couldn't open that file.");
      if (t === undefined) return;
      setText(t);
      setFilename(file.name);
      setAiLabelled(false);
    },
    /** Loads the sample transcript and reads it straight away. */
    loadSample: async () => {
      const res = await run("sample", api.callsSample, "Couldn't load the sample call.");
      if (res) await load(res.text, res.filename, false);
    },
    read: () => read({ text, filename }),
    /** "That's me": read the same call again with this speaker as the learner. Edits to the prospect start over. */
    pickRep: (rep: string) => result && read({ ...result.source, rep }),
    edit: (patch: Partial<ProspectDraft>) => setDraft((d) => d && { ...d, ...patch }),
    /** Back to the transcript box (the text stays). */
    back: () => {
      cancel();
      setResult(null);
      setDraft(null);
    },
    acceptAll,
  };
}

export type CallReader = ReturnType<typeof useCallReader>;
