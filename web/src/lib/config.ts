// Tunable values for the whole frontend. Change behaviour here, not in components.

export const config = {
  /** API lives on the same origin (Flask serves the built app; dev proxies /api). */
  apiBase: "",
  /** DOM id of the sidebar (target of the mobile "Panels" button). */
  ids: { panels: "session-panels" },
  chatTimeoutMs: 25_000,
  slowReplyMs: 5_000,
  toastMs: 4_000,
  /** How long the feedback dialog shows "thanks" before closing. */
  feedbackThanksMs: 1_500,
  /** Character caps below mirror config/limits.yaml; the server enforces the same numbers. */
  maxMessageLength: 1_000,
  maxFeedbackLength: 500,
  historyCap: 100,
  countUpMs: 800,
  voice: {
    silenceDelayMs: 500,
    ttsWatchdogMs: 15_000,
    puterLoadMs: 15_000,
    maxRecordingMs: 60_000,
    restartBackoffMs: { base: 200, max: 5_000, attempts: 5 },
    speedRange: { min: -50, max: 50, step: 5 },
    language: "en-US",
    nativeRestartMs: 100,
    /** Browser speech-synthesis rate limits. */
    rateClamp: { min: 0.1, max: 10 },
  },
  /** Sell mode: readiness chip and the celebration when the AI buyer says yes. */
  sell: {
    deltaChipMs: 1_600,
    confetti: { count: 90, durationMs: 2_200, gravity: 0.18 },
    /** Grades that earn the celebration (together with a sale). */
    celebrateGrades: ["A"],
  },
  knowledge: { nameMax: 100, fieldMax: 1_000 },
  /** Buyer setup in sell mode: the learner's own objection (server caps at the same length) and quick picks. */
  chosenObjection: {
    max: 200,
    picks: [
      "It's too expensive for us right now.",
      "We already use someone for this.",
      "Call me back next quarter.",
      "I need to run it by my business partner.",
      "Just send me a brochure.",
      "We tried something like this before and it didn't work.",
    ],
  },
  coachTextMax: 120,
  /** Night-city film: light sizes, drift speed, glow and flicker. */
  film: {
    /** Lights are soft blurs, so 1x pixels look the same and cost a quarter. */
    maxDpr: 1,
    /** Redraw at most this often (~30fps); speeds are per 60fps frame. */
    frameMs: 33,
    baseFrameMs: 1000 / 60,
    yMin: 0.3,
    radius: { min: 10, span: 40 },
    speed: { min: 0.00015, span: 0.0007 },
    alpha: { min: 0.1, span: 0.22 },
    phaseSpan: 6,
    wrapAt: 1.1,
    flickerMs: 700,
    flickerBase: 0.7,
    flickerDepth: 0.3,
    lightness: "90%, 65%",
  },
  /** Page addresses, so links never hard-code paths. */
  routes: { home: "/", buy: "/buy/", sell: "/sell/", knowledge: "/knowledge/" },
  /** A missing page sends you home after this long, unless you choose to stay. */
  notFound: { redirectSeconds: 30 },
  landing: { wordRotateMs: 2_200, demoStepMs: 1_800, revealThreshold: 0.15 },
  drills: { intervalsDays: [0, 1, 3, 7, 21] },
  readinessBands: { low: 30, mid: 60 },
  quizBands: { correct: 70, partial: 40, stage: { correct: 100, partial: 50 } },
} as const;

/**
 * Every localStorage key in one place. When a name here changes, keep the old STRING
 * (e.g. coachStyle is stored as "trainingStyle") so learners keep their saved settings.
 */
export const storageKeys = {
  buySessionId: "salesRoleplaySessionId",
  sidebarTab: "sidebarTab",
  sellSettings: "sellSettings",
  coachStyle: "trainingStyle",
  ttsSpeed: "ttsPlaybackSpeed",
  autoSendDictation: "autoSendDictation",
  helpSeen: "helpSeen",
  drillSchedule: "drillSchedule.v1",
  debug: "debug",
} as const;
