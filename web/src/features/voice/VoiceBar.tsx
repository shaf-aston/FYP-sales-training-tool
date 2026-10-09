"use client";

// Voice controls above the message box: hands-free toggle, dictate, stop, and a live status strip.

import { Button, Notice, VoiceWave } from "@/components/ui";
import { useVoice } from "./VoiceContext";
import s from "./VoiceBar.module.css";

const UNSUPPORTED_HINT = "Dictation needs Chrome, Edge or Safari. You can still type.";

export function VoiceBar() {
  const v = useVoice();
  const micOff = !v.supported;
  const busy = v.transcribing;

  return (
    <div className={s.wrap}>
      <div className={s.strip} aria-live="polite">
        {v.speaking ? (
          <span className={`${s.status} ${s.speaking}`}>
            <VoiceWave />
            Reading the reply aloud. Mic paused.
          </span>
        ) : v.transcribing ? (
          <Notice kind="loading">Transcribing, please wait...</Notice>
        ) : v.interim.trim() ? (
          <span className={s.status}>{v.interim}</span>
        ) : null}
      </div>
      <div className={s.row}>
        <Button
          variant="pill"
          pressed={v.handsFree}
          disabled={micOff}
          onClick={v.toggleHandsFree}
          title={micOff ? UNSUPPORTED_HINT : "Speak, auto-send, and hear the reply"}
        >
          Hands-free: {v.handsFree ? "on" : "off"}
        </Button>
        <Button
          variant="pill"
          pressed={v.dictating}
          disabled={micOff || busy}
          onClick={v.toggleDictation}
          className={v.dictating ? s.recording : undefined}
          title={micOff ? UNSUPPORTED_HINT : undefined}
        >
          {v.dictating ? "Stop" : "Dictate"}
        </Button>
        {v.speaking && (
          <Button variant="danger" aria-label="Interrupt assistant" onClick={v.interrupt}>
            Stop
          </Button>
        )}
        {micOff && <span className={s.hint}>{UNSUPPORTED_HINT}</span>}
      </div>
    </div>
  );
}

/** Small "Listen" button for one message: reads it aloud, or stops if it is already playing. */
export function ListenButton({ text }: { text: string }) {
  const v = useVoice();
  if (!v.ttsSupported) return null;
  return (
    <Button
      variant="ghost"
      pressed={v.speaking}
      onClick={() => (v.speaking ? v.stop() : v.speak(text))}
      aria-label={v.speaking ? "Stop listening" : "Listen to this message"}
    >
      {v.speaking ? "Stop" : "Listen"}
    </Button>
  );
}
