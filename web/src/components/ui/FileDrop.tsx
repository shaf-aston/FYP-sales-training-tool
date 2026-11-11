"use client";

import { useId, useState, type DragEvent } from "react";
import { Icon } from "./Icon";
import s from "./FileDrop.module.css";

interface Props {
  /** File extensions the picker offers, e.g. [".txt", ".vtt"]. Dropped files are not filtered: check them in onFile. */
  accept: readonly string[];
  onFile: (file: File) => void;
  /** What to drop, e.g. "Drop your SOP"; the zone adds "or choose a file". */
  prompt: string;
  /** A small line under the prompt, e.g. the file types and size limit. */
  hint?: string;
  /** Replaces the prompt while a dropped file is being opened or sent. */
  busyLabel?: string;
}

/** A box to drop one file on, or click / press Enter to choose one. */
export function FileDrop({ accept, onFile, prompt, hint, busyLabel }: Props) {
  const id = useId();
  const [over, setOver] = useState(false);

  const hover = (e: DragEvent) => {
    e.preventDefault(); // without this the browser opens the file instead of dropping it here
    setOver(true);
  };
  const leave = (e: DragEvent) => {
    if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(false);
  };
  const drop = (e: DragEvent) => {
    e.preventDefault();
    setOver(false);
    const file = e.dataTransfer.files[0];
    if (file) onFile(file);
  };

  return (
    <div className={`${s.zone} ${over ? s.over : ""}`} onDragEnter={hover} onDragOver={hover} onDragLeave={leave} onDrop={drop}>
      <input
        id={id}
        type="file"
        accept={accept.join(",")}
        className={`sr-only ${s.input}`}
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = ""; // choosing the same file again still fires
          if (file) onFile(file);
        }}
      />
      <label htmlFor={id} className={s.label}>
        <Icon name="upload" />
        {busyLabel ?? (
          <span>
            {prompt} or <span className={s.choose}>choose a file</span>
          </span>
        )}
        {hint && <span className={s.hint}>{hint}</span>}
      </label>
    </div>
  );
}
