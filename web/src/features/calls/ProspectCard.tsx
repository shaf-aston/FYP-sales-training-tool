"use client";

import { useId } from "react";
import { Card, ChipList, Segmented, TextArea, TextInput } from "@/components/ui";
import { difficultyOptions } from "@/features/sell/options";
import type { CallProfile } from "@/lib/api/types";
import { config } from "@/lib/config";
import { ObjectionList } from "./ObjectionList";
import type { ProspectDraft } from "./useCallReader";
import s from "./ProspectCard.module.css";

interface Props {
  draft: ProspectDraft;
  /** Why each field says what it says: short quotes or reasons from the call, by field name. */
  evidence: CallProfile["evidence"];
  onEdit: (patch: Partial<ProspectDraft>) => void;
}

const { nameMax, textMax, itemMax, maxItems } = config.calls.prospect;

/** The prospect read from the call, every field editable, with a quiet "from the call" note under each. */
export function ProspectCard({ draft, evidence, onEdit }: Props) {
  const titleId = useId();
  const from = (field: string) => {
    const quotes = evidence[field]?.slice(0, config.calls.evidenceShown);
    return quotes?.length ? <span className={s.evidence}>From the call: {quotes.join(" · ")}</span> : undefined;
  };

  return (
    <Card className={s.card} aria-labelledby={titleId}>
      <h3 id={titleId} className={s.title}>
        The prospect
      </h3>
      <TextInput label="Name" value={draft.name} maxLength={nameMax} hint={from("name")} onChange={(e) => onEdit({ name: e.target.value })} />
      <TextArea
        label="Background"
        rows={2}
        value={draft.background}
        maxLength={textMax}
        hint={from("background")}
        onChange={(e) => onEdit({ background: e.target.value })}
      />
      <TextArea
        label="Personality"
        rows={2}
        value={draft.personality}
        maxLength={textMax}
        hint={from("personality")}
        onChange={(e) => onEdit({ personality: e.target.value })}
      />
      <TextArea
        label="Budget"
        rows={2}
        value={draft.budget}
        maxLength={textMax}
        hint={from("budget")}
        onChange={(e) => onEdit({ budget: e.target.value })}
      />
      <ChipList
        label="Needs"
        noun="need"
        items={draft.needs}
        maxLength={itemMax}
        maxItems={maxItems}
        hint={from("needs")}
        onChange={(needs) => onEdit({ needs })}
      />
      <ChipList
        label="Pain points"
        noun="pain point"
        items={draft.pain_points}
        maxLength={itemMax}
        maxItems={maxItems}
        hint={from("pain_points")}
        onChange={(pain_points) => onEdit({ pain_points })}
      />
      <ObjectionList items={draft.objections} onChange={(objections) => onEdit({ objections })} />
      <div className={s.field}>
        <Segmented label="Difficulty" options={[...difficultyOptions]} value={draft.difficulty} onChange={(difficulty) => onEdit({ difficulty })} />
        {from("difficulty")}
      </div>
    </Card>
  );
}
