"use client";

// Step 1 of SOP review: the learner's SOP (a file, pasted text or the sample) and the server's reading of it.

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { SopReadRes } from "@/lib/api/types";
import { config } from "@/lib/config";
import { hasExt, listOf, megabytes } from "@/lib/files";
import { useJob } from "@/lib/useJob";

const { accept, maxBytes } = config.sop;

/** `sample`: what "Try a sample SOP" loads (default: the SOP review's sample). */
export function useSopReader(sample: () => Promise<{ text: string; filename: string }> = api.sopSample) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<SopReadRes | null>(null);
  /** Where the SOP came from (a file name or "Pasted SOP"), shown above the result. */
  const [source, setSource] = useState("");
  /** Counts reads, so what was checked against an older SOP starts over. */
  const [version, setVersion] = useState(0);
  const { busy, error, setError, run, cancel } = useJob<"read" | "sample">();

  const read = async (sop: Parameters<typeof api.sopRead>[0], from: string) => {
    const res = await run("read", () => api.sopRead(sop), "Couldn't read that SOP. Try again.");
    if (!res) return;
    setResult(res);
    setSource(from);
    setVersion((v) => v + 1);
  };

  return {
    text,
    setText,
    result,
    source,
    version,
    busy,
    error,
    /** A dropped or chosen SOP file is read at once (PDF and Word are read on the server). */
    loadFile: (file: File) => {
      if (!hasExt(file, accept)) return setError(`Use a ${listOf(accept)} file.`);
      if (file.size > maxBytes) return setError(`That file is over ${megabytes(maxBytes)}.`);
      return read({ file }, file.name);
    },
    readText: () => read({ text }, "Pasted SOP"),
    /** The sample SOP goes in the box and is read at once. */
    loadSample: async () => {
      const res = await run("sample", sample, "Couldn't load the sample SOP.");
      if (!res) return;
      setText(res.text);
      await read({ text: res.text }, res.filename);
    },
    /** Back to the SOP box (the text stays). */
    back: () => {
      cancel();
      setResult(null);
    },
  };
}

export type SopReader = ReturnType<typeof useSopReader>;
