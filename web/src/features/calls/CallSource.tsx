"use client";

import { Button, FileDrop, Icon, Notice, TextArea } from "@/components/ui";
import { config } from "@/lib/config";
import type { CallReader } from "./useCallReader";
import s from "./CallSource.module.css";

/** Step one: drop, choose or paste a transcript (or load the sample), then read it. */
export function CallSource({ reader, onCancel }: { reader: CallReader; onCancel?: () => void }) {
  const { text, filename, busy, error } = reader;
  return (
    <div className={s.stack}>
      <FileDrop accept={config.calls.accept} onFile={reader.loadFile}>
        <Icon name="upload" />
        <span>
          {busy === "file" ? "Opening…" : "Drop a transcript or "}
          {busy !== "file" && <span className={s.choose}>choose a file</span>}
        </span>
        <span className={s.types}>{reader.acceptList}</span>
      </FileDrop>

      <TextArea
        label="Or paste the call"
        rows={6}
        value={text}
        placeholder={"Sam: Thanks for making the time.\nDana: Sure. We've got twenty minutes."}
        hint={filename && `From ${filename}`}
        onChange={(e) => reader.setText(e.target.value)}
      />

      {error && <Notice kind="error">{error}</Notice>}

      <Button variant="primary" block busy={busy === "read"} busyLabel="Reading…" disabled={!text.trim() || !!busy} onClick={reader.read}>
        Read call
      </Button>
      <button type="button" className={s.sample} disabled={!!busy} onClick={reader.loadSample}>
        {busy === "sample" ? "Loading the sample…" : "Try a sample call"}
      </button>
      {onCancel && (
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      )}
    </div>
  );
}
