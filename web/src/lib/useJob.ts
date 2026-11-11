"use client";

import { useRef, useState } from "react";
import { errorText } from "@/lib/api/client";

/**
 * One request at a time with its busy state and error: `run` marks what is busy, shows the server's error (or the
 * fallback), and drops a late answer once a newer job or `cancel` has replaced it.
 */
export function useJob<K extends string>() {
  const [busy, setBusy] = useState<K | null>(null);
  const [error, setError] = useState("");
  const ticket = useRef(0);

  /** Resolves the job's result, or undefined when it failed or was replaced. */
  const run = async <R>(kind: K, job: () => Promise<R>, fallback: string): Promise<R | undefined> => {
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

  /** Forget the job in flight and any error. */
  const cancel = () => {
    ticket.current++;
    setBusy(null);
    setError("");
  };

  return { busy, error, setError, run, cancel };
}
