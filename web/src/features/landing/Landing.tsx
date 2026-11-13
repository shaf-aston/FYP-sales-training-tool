"use client";

// Landing page: night-city film behind neon motion, a live demo, and a try-it challenge.
// Copy lives in content.ts; timings in config.landing; colours in tokens.css.

import Link from "next/link";
import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { AmbientFilm } from "@/components/film/AmbientFilm";
import { buttonClass, TypingDots } from "@/components/ui";
import { config } from "@/lib/config";
import { challenge, demoChat, features, heroWords, objections, steps } from "./content";
import s from "./Landing.module.css";
import { prefersReducedMotion } from "@/lib/motion";

const { routes, landing } = config;

/** Ticks 0..length-1 forever; stays at `still` when the viewer asked for less motion. */
function useTicker(length: number, ms: number, still = 0) {
  const [i, setI] = useState(still);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const id = setInterval(() => setI((n) => (n + 1) % length), ms);
    return () => clearInterval(id);
  }, [length, ms]);
  return i;
}

/** Writes the pointer position (px inside the element) into CSS variables, at most once per frame. */
let pending = 0;
function trackPointer(e: PointerEvent<HTMLElement>) {
  const el = e.currentTarget;
  const { clientX, clientY } = e;
  cancelAnimationFrame(pending);
  pending = requestAnimationFrame(() => {
    const r = el.getBoundingClientRect();
    el.style.setProperty("--mx", `${clientX - r.left}px`);
    el.style.setProperty("--my", `${clientY - r.top}px`);
  });
}

function LiveDemo() {
  // Each message: typing dots, then the bubble. After the last one the chat
  // holds, fades out, and restarts, so nothing ever snaps away.
  const n = demoChat.length;
  const [step, setStep] = useState(n * 2); // even = typing, odd = shown; n*2 = hold
  const [leaving, setLeaving] = useState(false);
  useEffect(() => {
    if (prefersReducedMotion()) return;
    const typingMs = landing.demoStepMs * 0.45;
    let id: ReturnType<typeof setTimeout>;
    if (leaving) {
      id = setTimeout(() => { setLeaving(false); setStep(0); }, 600);
    } else if (step >= n * 2) {
      id = setTimeout(() => setLeaving(true), landing.demoStepMs * 1.5);
    } else {
      id = setTimeout(() => setStep(step + 1), step % 2 === 0 ? typingMs : landing.demoStepMs);
    }
    return () => clearTimeout(id);
  }, [step, leaving, n]);

  const visible = Math.ceil(step / 2);
  const typing = !leaving && step < n * 2 && step % 2 === 0 ? demoChat[step / 2] : null;
  return (
    <div className={s.demo} aria-label="Example practice chat" role="img">
      <div className={s.demoBar}>
        <span className={s.dot} />
        <span>Live practice</span>
        <span className={s.stage}>Stage · Objection</span>
      </div>
      {/* the whole chat, hidden, sizes the box: restarting the loop never shrinks it and moves the page (phone) */}
      <div className={s.threadSlot}>
        <div className={`${s.thread} ${s.threadSizer}`} aria-hidden="true">
          {demoChat.map((m, i) => (
            <p key={i} className={`${s.bubble} ${s[m.who]}`}>
              {m.text}
            </p>
          ))}
        </div>
        <div className={s.thread} data-leaving={leaving || undefined}>
          {demoChat.slice(0, visible).map((m, i) => (
            <p key={i} className={`${s.bubble} ${s[m.who]}`}>
              {m.text}
            </p>
          ))}
          {typing && (
            <span className={`${s.bubble} ${s.typing} ${s[typing.who]}`}>
              <TypingDots />
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

function Challenge() {
  const [pick, setPick] = useState<number | null>(null);
  const chosen = pick === null ? null : challenge.options[pick];
  return (
    <div className={s.challenge} data-reveal>
      <p className={s.kicker}>Try it now · no sign-up</p>
      <h2 className={s.h2}>The buyer says {challenge.buyer}</h2>
      <div className={s.options}>
        {challenge.options.map((o, i) => (
          <button
            key={o.text}
            type="button"
            className={s.option}
            data-picked={pick === i || undefined}
            data-good={o.score >= 70 || undefined}
            onClick={() => setPick(i)}
            aria-pressed={pick === i}
          >
            {o.text}
          </button>
        ))}
      </div>
      <div className={s.verdict} aria-live="polite">
        {chosen ? (
          <>
            <span className={s.score} data-good={chosen.score >= 70 || undefined} style={{ "--score": chosen.score } as CSSProperties}>
              {chosen.score}
            </span>
            <p>{chosen.verdict}</p>
          </>
        ) : (
          <p>Pick a reply: the coach scores it instantly.</p>
        )}
      </div>
    </div>
  );
}

export function Landing() {
  const word = useTicker(heroWords.length, landing.wordRotateMs);
  const root = useRef<HTMLDivElement>(null);

  // Sections fade up the first time they scroll into view.
  useEffect(() => {
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && (e.target as HTMLElement).setAttribute("data-shown", "")),
      { threshold: landing.revealThreshold },
    );
    root.current?.querySelectorAll("[data-reveal]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, []);

  return (
    <div ref={root} className={s.page}>
      <AmbientFilm />
      <div className={s.progress} aria-hidden="true" />

      <header className={s.nav}>
        <span className={`${s.brand} neon-text`}>Eloquence</span>
        <nav className={s.links} aria-label="Main">
          <a href="#how">How it works</a>
          <a href="#try">Try it</a>
          <Link href={routes.buy} className={buttonClass("primary")}>
            Practise buying
          </Link>
        </nav>
      </header>

      <main>
        <section className={s.hero} onPointerMove={trackPointer}>
          <div className={s.orbs} aria-hidden="true">
            <span /> <span /> <span />
          </div>
          <div className={s.heroCopy}>
            <p className={s.kicker}>Sales call practice</p>
            <h1 className={s.h1}>
              <span className={s.heroLine}>Get good at</span>
              {/* every word sizes the slot, so a longer one never wraps the line and moves the page (phone CLS 0.17) */}
              <span className={s.wordSlot}>
                {heroWords.map((w) => (
                  <span key={w} className={s.wordSizer} aria-hidden="true">
                    {w}
                  </span>
                ))}
                <span key={word} className={`${s.word} neon-text`}>
                  {heroWords[word]}
                </span>
              </span>
              <span className={s.heroLine}>before the real call.</span>
            </h1>
            <p className={s.lead}>Roleplay a sales call from either side: buy from a virtual rep, or sell to a buyer who pushes back. Every move gets feedback. Ten minutes a day.</p>
            <div className={s.ctas}>
              <Link href={routes.buy} className={buttonClass("primary", s.bigCta)}>
                Practise buying →
              </Link>
              <Link href={routes.sell} className={buttonClass("pill")}>
                Practise selling
              </Link>
            </div>
          </div>
          <LiveDemo />
        </section>

        <div className={s.marquee} aria-label="Objections you will practise">
          <div className={s.track}>
            {[...objections, ...objections].map((o, i) => (
              <span key={i} className={s.chip} aria-hidden={i >= objections.length || undefined}>
                {o}
              </span>
            ))}
          </div>
        </div>

        <section id="how" className={s.section}>
          <h2 className={`${s.h2} ${s.center}`} data-reveal>
            Three steps. <span className="neon-text">Real nerves.</span>
          </h2>
          <ol className={s.steps}>
            {steps.map((st, i) => (
              <li key={st.tag} className={s.step} data-reveal style={{ "--i": i } as CSSProperties}>
                <div className={`${s.scene} ${s[st.scene]}`} aria-hidden="true">
                  <span /> <span /> <span /> <span /> <span /> <span /> <span />
                </div>
                <span className={s.tag}>{st.tag}</span>
                <h3>{st.title}</h3>
                <p>{st.text}</p>
              </li>
            ))}
          </ol>
        </section>

        <section className={s.section}>
          <div className={s.features}>
            {features.map((f, i) => (
              <article
                key={f.title}
                className={s.feature}
                data-reveal
                onPointerMove={trackPointer}
                style={{ "--hue": f.hue, "--i": i % 3 } as CSSProperties}
              >
                <h3>{f.title}</h3>
                <p>{f.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section id="try" className={s.section}>
          <Challenge />
        </section>

        <section className={s.final} data-reveal>
          <h2 className={s.h1}>
            Your next buyer is <span className="neon-text">waiting.</span>
          </h2>
          <div className={s.ctas}>
            <Link href={routes.buy} className={buttonClass("primary", s.bigCta)}>
              Practise buying →
            </Link>
            <Link href={routes.sell} className={buttonClass("pill")}>
              Practise selling
            </Link>
          </div>
        </section>
      </main>

      <footer className={s.footer}>
        <span className={`${s.brand} neon-text`}>Eloquence</span>
        <nav className={s.links} aria-label="Footer">
          <Link href={routes.buy}>Buy mode</Link>
          <Link href={routes.sell}>Sell mode</Link>
          <Link href={`${routes.knowledge}?mode=sell`}>Knowledge base</Link>
          <a href="#try">Try an objection</a>
        </nav>
      </footer>
    </div>
  );
}
