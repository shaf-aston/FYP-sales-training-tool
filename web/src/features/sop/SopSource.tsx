"use client";

import { Button, FileDrop, Notice, TextArea, TextButton } from "@/components/ui";
import { config } from "@/lib/config";
import { megabytes } from "@/lib/files";
import type { SopReader } from "./useSopReader";
import s from "./Sop.module.css";

/** Step 1: drop or paste the team's SOP, or try the sample. A file or the sample is read at once. */
export function SopSource({ reader }: { reader: SopReader }) {
  const { text, busy, error } = reader;
  return (
    <div className={s.stack}>
      <FileDrop
        accept={config.sop.accept}
        onFile={reader.loadFile}
        prompt="Drop your SOP"
        hint={`${config.sop.accept.join(" ")} · up to ${megabytes(config.sop.maxBytes)}`}
        busyLabel={busy === "read" ? "Reading your SOP…" : undefined}
      />
      <TextArea
        label="Or paste it"
        rows={6}
        value={text}
        placeholder={"## Discover\n- Ask what made them book the call\n- Ask who else signs off"}
        onChange={(e) => reader.setText(e.target.value)}
      />
      {error && <Notice kind="error">{error}</Notice>}
      <Button variant="primary" block busy={busy === "read"} busyLabel="Reading…" disabled={!text.trim() || !!busy} onClick={reader.readText}>
        Read SOP
      </Button>
      <TextButton className={s.sample} disabled={!!busy} onClick={reader.loadSample}>
        {busy === "sample" ? "Loading the sample…" : "Try a sample SOP"}
      </TextButton>
    </div>
  );
}
