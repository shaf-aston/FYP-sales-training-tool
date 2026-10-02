"use client";

// Settings tab: auto-send after a pause, and how fast the coach talks.

import { useId } from "react";
import { Switch, useToast } from "@/components/ui";
import { config } from "@/lib/config";
import { useVoice } from "./VoiceContext";
import s from "./VoiceSettings.module.css";

const speedCaption = (n: number) => (n < 0 ? `Slower (${n}%)` : n > 0 ? `Faster (+${n}%)` : "Normal");

export function VoiceSettings() {
  const { autoSend, setAutoSend, speed, setSpeed, ttsSupported } = useVoice();
  const toast = useToast();
  const id = useId();
  const { min, max, step } = config.voice.speedRange;

  return (
    <div className={s.wrap}>
      <Switch
        label="Auto-send after you pause speaking"
        checked={autoSend}
        onChange={(on) => {
          setAutoSend(on);
          toast(`Auto-send after pause ${on ? "ON" : "OFF"}`, "info");
        }}
      />
      <div className={s.speed}>
        <label htmlFor={id} className={s.label}>
          Coach voice speed
        </label>
        <input
          id={id}
          className={s.slider}
          type="range"
          min={min}
          max={max}
          step={step}
          value={speed}
          disabled={!ttsSupported}
          aria-valuetext={speedCaption(speed)}
          onChange={(e) => setSpeed(Number(e.target.value))}
        />
        <div className={s.ends} aria-hidden="true">
          <span>Slower</span>
          <span className={s.caption}>{speedCaption(speed)}</span>
          <span>Faster</span>
        </div>
        {!ttsSupported && <p className={s.hint}>This browser cannot read replies aloud.</p>}
      </div>
    </div>
  );
}
