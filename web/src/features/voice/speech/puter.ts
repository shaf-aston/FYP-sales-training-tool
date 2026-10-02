// Puter.js (free speech-to-text / text-to-speech fallback). Loaded once, on first use, never at page load.

export interface PuterAi {
  speech2txt(opts: { file: Blob; model: string }): Promise<{ text?: string } | string>;
  txt2speech(text: string, opts: { language: string; engine: string }): Promise<HTMLAudioElement>;
}
interface Puter {
  ai: PuterAi;
}

declare global {
  interface Window {
    puter?: Puter;
  }
}

const SCRIPT_URL = "https://js.puter.com/v2/";
let loading: Promise<PuterAi> | null = null;

/** Resolves with puter.ai, or rejects (and allows a retry) if the script can't load within timeoutMs. */
export function loadPuter(timeoutMs: number): Promise<PuterAi> {
  if (typeof window === "undefined") return Promise.reject(new Error("Puter needs a browser"));
  if (window.puter?.ai) return Promise.resolve(window.puter.ai);
  if (loading) return loading;

  loading = new Promise<PuterAi>((resolve, reject) => {
    const fail = (why: string) => {
      loading = null;
      script.remove();
      reject(new Error(why));
    };
    const script = document.createElement("script");
    script.src = SCRIPT_URL;
    script.async = true;
    const timer = setTimeout(() => fail("Puter took too long to load"), timeoutMs);
    script.onload = () => {
      clearTimeout(timer);
      if (window.puter?.ai) resolve(window.puter.ai);
      else fail("Puter loaded but is not ready");
    };
    script.onerror = () => {
      clearTimeout(timer);
      fail("Could not load Puter");
    };
    document.head.appendChild(script);
  });
  return loading;
}
