"use client";

import { Button, FileDrop, Notice, TextArea, TextButton } from "@/components/ui";
import type { SopStage } from "@/lib/api/types";
import { StepResults } from "./StepResults";
import { useCallCheck } from "./useCallCheck";
import s from "./Sop.module.css";

/** Step 2: a real call's transcript, checked against the SOP that was just read. */
export function CallCheck({ stages }: { stages: SopStage[] }) {
  const c = useCallCheck(stages);

  if (c.result)
    return (
      <div className={s.stack}>
        <StepResults result={c.result} />
        <Button variant="ghost" className={s.start} onClick={c.back}>
          Check another call
        </Button>
      </div>
    );

  return (
    <div className={s.stack}>
      <FileDrop
        accept={c.accept}
        onFile={c.loadFile}
        prompt="Drop a call transcript"
        hint={c.accept.join(" ")}
        busyLabel={c.busy === "file" ? "Opening…" : undefined}
      />
      <TextArea
        label="Or paste the call"
        rows={5}
        value={c.text}
        placeholder={"Sam: Thanks for making the time.\nDana: Sure. We've got twenty minutes."}
        onChange={(e) => c.setText(e.target.value)}
      />
      {c.error && <Notice kind="error">{c.error}</Notice>}
      <Button variant="primary" block busy={c.busy === "check"} busyLabel="Checking…" disabled={!c.text.trim() || !!c.busy} onClick={c.check}>
        Check the call
      </Button>
      <TextButton className={s.sample} disabled={!!c.busy} onClick={c.loadSample}>
        {c.busy === "sample" ? "Loading the sample…" : "Try a sample call"}
      </TextButton>
    </div>
  );
}
