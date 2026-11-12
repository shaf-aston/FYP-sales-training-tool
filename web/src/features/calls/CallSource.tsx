"use client";

import { Button, FileDrop, Notice, TextArea, TextButton } from "@/components/ui";
import { config } from "@/lib/config";
import { megabytes } from "@/lib/files";
import type { CallReader } from "./useCallReader";
import s from "./CallSource.module.css";

/** Step one: drop, choose or paste a transcript (or load the sample), then read it. */
export function CallSource({
  reader,
  onCancel,
  privacy = "Read on our server and never stored. Save a prospect to keep it.",
}: {
  reader: CallReader;
  onCancel?: () => void;
  /** What happens to the call: shown under the box. */
  privacy?: string;
}) {
  const { text, filename, busy, error } = reader;
  return (
    <div className={s.stack}>
      <FileDrop
        accept={reader.acceptAll}
        onFile={reader.loadFile}
        prompt="Drop a transcript or recording,"
        hint={`Transcripts: ${config.calls.accept.join(" ")} · Recordings: .mp3 .m4a .wav and more, up to ${megabytes(config.calls.audio.maxBytes)}`}
        busyLabel={busy === "file" ? "Opening…" : busy === "audio" ? "Uploading the recording…" : undefined}
      />
      {busy === "audio" && <Notice kind="loading">Turning the recording into text… about a minute per hour of audio</Notice>}

      <TextArea
        label="Or paste the call"
        rows={6}
        value={text}
        placeholder={"Sam: Thanks for making the time.\nDana: Sure. We've got twenty minutes."}
        hint={filename && `From ${filename}`}
        onChange={(e) => reader.setText(e.target.value)}
      />
      <p className={s.privacy}>{privacy}</p>

      {error && <Notice kind="error">{error}</Notice>}

      <Button variant="primary" block busy={busy === "read"} busyLabel="Reading…" disabled={!text.trim() || !!busy} onClick={reader.read}>
        Read call
      </Button>
      <TextButton className={s.sample} disabled={!!busy} onClick={reader.loadSample}>
        {busy === "sample" ? "Loading the sample…" : "Try a sample call"}
      </TextButton>
      {onCancel && (
        <Button variant="ghost" onClick={onCancel}>
          Cancel
        </Button>
      )}
    </div>
  );
}
