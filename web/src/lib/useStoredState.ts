"use client";

import { useEffect, useState } from "react";
import { readString, writeString } from "./storage";

/**
 * useState that survives reloads via localStorage. Starts from `initial` on the server
 * and first client render (avoids hydration mismatch), then loads the saved value.
 */
export function useStoredState<T>(key: string, initial: T, parse: (raw: string) => T | undefined = defaultParse) {
  const [value, setValue] = useState<T>(initial);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const raw = readString(key);
    const saved = raw === null ? undefined : parse(raw);
    // eslint-disable-next-line react-hooks/set-state-in-effect -- one-time load from storage after hydration
    if (saved !== undefined) setValue(saved);
    setLoaded(true);
  }, [key, parse]);

  useEffect(() => {
    if (loaded) writeString(key, typeof value === "string" ? value : JSON.stringify(value));
  }, [key, value, loaded]);

  return [value, setValue] as const;
}

function defaultParse<T>(raw: string): T | undefined {
  try {
    return JSON.parse(raw) as T;
  } catch {
    return raw as unknown as T;
  }
}
