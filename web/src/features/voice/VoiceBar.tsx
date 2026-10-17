"use client";

// Voice controls inside the message box: hands-free toggle, dictate, stop, and a live status strip above it.

import { Button, Icon, Notice, VoiceWave } from "@/components/ui";
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
          className={s.icon}
          aria-label={v.handsFree ? "Turn hands-free off" : "Turn hands-free on"}
          title={micOff ? UNSUPPORTED_HINT : "Hands-free: speak, auto-send, and hear the reply"}
        >
          <Icon name="wave" />
        </Button>
        <Button
          variant="pill"
          pressed={v.dictating}
          disabled={micOff || busy}
          onClick={v.toggleDictation}
          className={`${s.icon} ${v.dictating ? s.recording : ""}`}
          aria-label={v.dictating ? "Stop dictating" : "Dictate"}
          title={micOff ? UNSUPPORTED_HINT : v.dictating ? "Stop dictating" : "Dictate"}
        >
          <Icon name={v.dictating ? "stop" : "mic"} />
        </Button>
        {v.speaking && (
          <Button variant="danger" aria-label="Interrupt assistant" onClick={v.interrupt}>
            Stop
          </Button>
        )}
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
      aria-label={v.speaking ? "Stop reading aloud" : "Read this message aloud"}
      title={v.speaking ? "Stop" : "Read aloud"}
    >
      <Icon name={v.speaking ? "stop" : "speaker"} size={16} />
    </Button>
  );
}
