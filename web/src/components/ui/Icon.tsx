// Small line icons drawn inline (no icon library). Colour follows the text colour.

const PATHS = {
  /** Two arrows trading places: switch between buying and selling. */
  swap: "M7 7h11l-3-3M17 17H6l3 3",
  /** A die: pick at random. */
  dice: "M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM8.5 8.5h.01M15.5 15.5h.01M12 12h.01",
  /** A person's head and shoulders: buy mode (you are the customer). */
  person: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  /** A speech bubble: sell mode (you do the talking). */
  speech: "M4 5h16v11H9l-5 4z",
  /** A microphone: dictate. */
  mic: "M12 3a3 3 0 0 1 3 3v6a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3zM5 11a7 7 0 0 0 14 0M12 18v3",
  /** Sound waves: hands-free (speak and hear replies). */
  wave: "M4 10v4M8 7v10M12 4v16M16 7v10M20 10v4",
  /** A speaker: read this message aloud. */
  speaker: "M4 9h4l5-4v14l-5-4H4zM17 9a4 4 0 0 1 0 6",
  /** A pencil: edit. */
  pencil: "M4 20h4L19 9l-4-4L4 16zM14 6l4 4",
  /** An arrow pointing up: send. */
  send: "M12 19V5M6 11l6-6 6 6",
  /** A square: stop. */
  stop: "M7 7h10v10H7z",
} as const;

type IconName = keyof typeof PATHS;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
