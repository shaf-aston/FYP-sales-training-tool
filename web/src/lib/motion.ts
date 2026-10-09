// One check for the OS "reduce motion" setting, used by every animation that runs in JS.

export const prefersReducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
