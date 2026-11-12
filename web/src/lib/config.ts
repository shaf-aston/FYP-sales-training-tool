// Tunable values for the whole frontend. Change behaviour here, not in components.

export const config = {
  /** API lives on the same origin (Flask serves the built app; dev proxies /api). */
  apiBase: "",
  api: {
    /**
     * Where call recordings are uploaded: straight to the API host, because the Vercel rewrite can't be trusted with
     * recordings up to 200 MB. The host is the one in web/public/vercel.json (keep them the same). On localhost the page and the
     * API share an origin, so "". The API's CORS allows the Vercel site, and a multipart POST needs no preflight.
     */
    uploadOrigin: () =>
      typeof location === "undefined" || ["localhost", "127.0.0.1"].includes(location.hostname) ? "" : "https://140-238-102-50.sslip.io",
  },
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
    ttsWatchdogMs: 30_000,
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
  /** Skill Radar: sessions kept on this device and how many make the recent average (targets come from the server). */
  /** historyCap matches the server's max_skill_entries (limits.yaml), so a synced history fits the device whole. */
  skills: { historyCap: 200, averageWindow: 5 },
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
  /** A real call the learner brings in (sell mode, Buyer tab). The server caps the transcript length itself. */
  calls: {
    /** File types the drop zone takes; the server reads WebVTT, SRT and "Name: line" text. */
    accept: [".txt", ".vtt", ".srt"],
    /** Bigger files are not transcripts; refuse before reading them into memory (limits.yaml max_request_bytes). */
    maxFileBytes: 1_000_000,
    /**
     * A call recording, turned into a transcript on the server (limits.yaml transcription: formats, max_upload_bytes).
     * Past 25 MB the server cuts it into parts; a server without ffmpeg refuses those and says so itself.
     */
    audio: {
      accept: [".mp3", ".m4a", ".mp4", ".mpeg", ".mpga", ".wav", ".webm", ".ogg", ".flac"],
      maxBytes: 200_000_000,
      /** Upload, speech to text (180 s a part at most) and speaker labels: a long call on a slow line needs minutes. */
      timeoutMs: 600_000,
    },
    /** Caps on the prospect fields the learner edits; the server allows 300 characters a field and 5 items a list (limits.yaml max_custom_buyer_*). */
    prospect: { nameMax: 60, textMax: 300, itemMax: 180, maxItems: 5 },
    /** Saved prospects listed before "Show all". */
    savedShown: 5,
    /** Quotes shown under a field as "from the call". */
    evidenceShown: 2,
    /** How the server guessed which speaker is the learner (rep.how). */
    repGuess: { named: "Named you", most_questions: "Asked the most questions", first_speaker: "Spoke first" },
    objectionTypes: { price: "Price", skepticism: "Doubt", timing: "Timing", partner: "Partner", fear: "Fear" },
  },
  /** SOP review: a team's sales SOP (limits.yaml sop: max_bytes; core/sop/document.py reads these types). */
  sop: {
    accept: [".pdf", ".docx", ".md", ".txt"],
    maxBytes: 5_000_000,
  },
  /** Optional account; the server checks the same limits (limits.yaml accounts). */
  account: { nameMax: 60, passwordMin: 8, teamNameMax: 60 },
  /** A saved prospect keeps no difficulty: practising one starts here. */
  savedProspectDifficulty: "medium",
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
  routes: { home: "/", buy: "/buy/", sell: "/sell/", knowledge: "/knowledge/", sop: "/sop/", google: "/api/account/google" },
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
  buyProduct: "buyProduct",
  /** sessionStorage: the rep's words for new calls ({ product, label, words }), set from the Rep's words tool. */
  buyWords: "buyWords",
  sidebarTab: "sidebarTab",
  sellSettings: "sellSettings",
  /** sessionStorage: the live sell call ({ id, pick }), so a reload or Back picks it up again. */
  sellCall: "sellCall",
  skillLog: "skillLog.v1",
  skillOwner: "skillLog.owner",
  skillTarget: "skillTarget",
  coachStyle: "trainingStyle",
  ttsSpeed: "ttsPlaybackSpeed",
  autoSendDictation: "autoSendDictation",
  helpSeen: "helpSeen",
  drillSchedule: "drillSchedule.v1",
  debug: "debug",
  /** The learner's product details for the sell-mode buyer (knowledge base page); sent with each new sell call. */
  knowledge: "knowledge.v1",
} as const;
