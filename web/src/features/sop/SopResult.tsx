"use client";

import { Button } from "@/components/ui";
import type { SopReadRes } from "@/lib/api/types";
import { Critique } from "./Critique";
import { ElementList } from "./ElementList";
import { ScoreTile } from "./ScoreTile";
import { SopOutline } from "./SopOutline";
import s from "./Sop.module.css";

/** What the SOP covers of a good call, and its outline as read. */
export function SopResult({ result, source, onBack }: { result: SopReadRes; source: string; onBack: () => void }) {
  const covered = result.elements.filter((e) => e.covered).length;
  return (
    <div className={s.stack}>
      <p className="sr-only" role="status">
        SOP read: it covers {covered} of {result.elements.length} elements of a good call.
      </p>
      <div className={s.head}>
        <p className={s.muted}>{source}</p>
        <Button variant="ghost" onClick={onBack}>
          Use another SOP
        </Button>
      </div>
      <Critique text={result.critique} />
      <div className={s.split}>
        <ScoreTile value={result.coverage} label="of a good call covered">
          <p className={s.muted}>
            {covered} of {result.elements.length} elements
          </p>
        </ScoreTile>
        <ElementList elements={result.elements} />
      </div>
      <h3 className={s.label}>Outline</h3>
      <SopOutline stages={result.stages} />
    </div>
  );
}
