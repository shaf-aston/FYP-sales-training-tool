"use client";

import { Button, FileDrop, Icon, Notice, TextArea } from "@/components/ui";
import { config } from "@/lib/config";
import { megabytes } from "@/lib/files";
import type { CallReader } from "./useCallReader";
import s from "./CallSource.module.css";

/** Step one: drop, choose or paste a transcript (or load the sample), then read it. */
export function CallSource({ reader, onCancel }: { reader: CallReader; onCancel?: () => void }) {
  const { text, filename, busy, error } = reader;
  return (
    <div className={s.stack}>
      <FileDrop accept={reader.acceptAll} onFile={reader.loadFile}>
        <Icon name="upload" />
        <span>
          {busy === "file" ? "Opening…" : "Drop a transcript or recording, or "}
          {busy !== "file" && <span className={s.choose}>choose a file</span>}
        </span>
        <span className={s.types}>
          {config.calls.accept.join(" ")} · recordings up to {megabytes(config.calls.audio.maxBytes)}
        </span>
      </FileDrop>
      {busy === "audio" && <Notice kind="loading">Turning the recording into text… about a minute per hour of audio</Notice>}

      <TextArea
        label="Or paste the call"
        rows={6}
        value={text}
        placeholder={"Sam: Thanks for making the time.\nDana: Sure. We've got twenty minutes."}
        hint={filename && `From ${filename}`}
        onChange={(e) => reader.setText(e.target.value)}
      />
      <p className={s.privacy}>Read on our server and never stored. Save a prospect to keep it.</p>

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
