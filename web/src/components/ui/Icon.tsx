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
