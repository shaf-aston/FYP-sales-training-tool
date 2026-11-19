"use client";

// Step 2 of SOP review: a real call's transcript (pasted, a text file or the sample call), checked against the SOP.

import { useState } from "react";
import { api } from "@/lib/api/client";
import type { SopCheckRes, SopStage } from "@/lib/api/types";
import { config } from "@/lib/config";
import { hasExt, listOf, readText } from "@/lib/files";
import { useJob } from "@/lib/useJob";

const { accept, maxFileBytes } = config.calls;

export function useCallCheck(stages: SopStage[]) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<SopCheckRes | null>(null);
  const { busy, error, setError, run, cancel } = useJob<"file" | "sample" | "check">();

  const check = async (call: string) => {
    const res = await run("check", () => api.sopCheck(stages, { text: call }), "Couldn't check that call. Try again.");
    if (res) setResult(res);
  };

  return {
    text,
    setText,
    result,
    busy,
    error,
    accept,
    check: () => check(text),
    /** A transcript file goes in the box to look over before it is checked. */
    loadFile: async (file: File) => {
      if (!hasExt(file, accept)) return setError(`Use a transcript: ${listOf(accept)}.`);
      if (file.size > maxFileBytes) return setError("That file is too big for one call.");
      const t = await run("file", () => readText(file), "Couldn't open that file.");
      if (t !== undefined) setText(t);
    },
    /** The sample call goes in the box and is checked at once. */
    loadSample: async () => {
      const res = await run("sample", api.callsSample, "Couldn't load the sample call.");
      if (!res) return;
      setText(res.text);
      await check(res.text);
    },
    /** Back to the transcript box (the text stays). */
    back: () => {
      cancel();
      setResult(null);
    },
  };
}

export type CallCheck = ReturnType<typeof useCallCheck>;
