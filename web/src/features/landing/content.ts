// Landing page words. Edit copy here; components only lay it out.

export const heroWords = ["price pushback", "cold calls", "“send me an email”", "the hard close", "awkward silences"];

export const objections = [
  "It's too expensive",
  "We already use someone",
  "Call me next quarter",
  "I need to ask my boss",
  "Just send me a brochure",
  "Not interested",
  "What's the catch?",
  "We tried this before",
];

/** One looping chat in the hero demo. `who` picks the bubble side. */
export const demoChat = [
  { who: "buyer", text: "Honestly, it's more than we budgeted for." },
  { who: "you", text: "Fair. What would it need to save you each month to be worth it?" },
  { who: "buyer", text: "Probably two days of admin work…" },
  { who: "coach", text: "Strong move: you turned price into value. +12" },
] as const;

export const steps = [
  { tag: "01", title: "Pick a buyer", text: "Choose the product, the buyer's mood and how tough they are. Every run plays out differently.", scene: "lights" },
  { tag: "02", title: "Talk it through", text: "Type or speak. The buyer pushes back, goes quiet, changes their mind, like a real call.", scene: "wave" },
  { tag: "03", title: "Get coached live", text: "A coach watches each turn, names the stage you're in and scores the moves that worked.", scene: "meter" },
] as const;

export const features = [
  { title: "Voice mode", text: "Speak out loud and hear the buyer answer back.", hue: "var(--neon-cyan)" },
  { title: "Live coach", text: "Stage, strategy and a score after every message.", hue: "var(--neon-amber)" },
  { title: "Sell mode", text: "You sell. The AI plays a buyer who pushes back.", hue: "var(--neon-cyan)" },
  { title: "Quick quizzes", text: "Short checks that explain why an answer works.", hue: "var(--neon-amber)" },
  { title: "Your product", text: "Load your own product notes so practice feels real.", hue: "var(--neon-cyan)" },
  { title: "Spaced drills", text: "Weak spots come back on day 1, 3, 7 and 21.", hue: "var(--neon-amber)" },
] as const;

/** The try-it game: one objection, three replies, instant verdicts. */
export const challenge = {
  buyer: "“We're happy with our current supplier.”",
  options: [
    { text: "Our product is much better than theirs.", score: 20, verdict: "Attacks their choice; buyers defend what they picked. Ask instead of argue." },
    { text: "Great, what do you like most about them?", score: 90, verdict: "Opens them up. Now you learn what matters and where the gap is." },
    { text: "No problem, I'll call back later.", score: 35, verdict: "Polite, but you gave up the call without learning anything." },
  ],
};
