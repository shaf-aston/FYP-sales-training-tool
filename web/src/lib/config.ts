// Tunable values for the whole frontend. Change behaviour here, not in components.

export const config = {
  /** API lives on the same origin (Flask serves the built app; dev proxies /api). */
  apiBase: "",
  chatTimeoutMs: 25_000,
  slowReplyMs: 5_000,
  toastMs: 4_000,
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
  prospect: {
    deltaChipMs: 1_600,
    confetti: { count: 90, durationMs: 2_200, gravity: 0.18 },
    /** Grades that earn the celebration (together with a sale). */
    celebrateGrades: ["A"],
  },
  knowledge: { nameMax: 100, fieldMax: 1_000 },
  coachTextMax: 120,
  /** Night-city film: light sizes, drift speed, glow and flicker. */
  film: {
    maxDpr: 2,
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
  routes: { home: "/", practice: "/practice/", knowledge: "/knowledge/" },
  landing: { wordRotateMs: 2_200, demoStepMs: 1_800, revealThreshold: 0.15 },
  drills: { intervalsDays: [0, 1, 3, 7, 21] },
  readinessBands: { low: 30, mid: 60 },
  quizBands: { correct: 70, partial: 40, stage: { correct: 100, partial: 50 } },
} as const;

/** Every localStorage key in one place. Values kept identical to the old UI so saved state carries over. */
export const storageKeys = {
  sessionId: "salesRoleplaySessionId",
  sidebarTab: "sidebarTab",
  trainingPanelOpen: "trainingPanelOpen",
  prospectSettings: "prospectSettings",
  trainingStyle: "trainingStyle",
  ttsSpeed: "ttsPlaybackSpeed",
  autoSendDictation: "autoSendDictation",
  helpSeen: "helpSeen",
  drillSchedule: "drillSchedule.v1",
  debug: "debug",
} as const;
