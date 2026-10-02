import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

// Flask serves the static build at / (backend/app.py `web_app`).
// In `npm run dev`, /api calls are proxied to Flask so both share one origin.
const FLASK_DEV_ORIGIN = "http://127.0.0.1:5000";

export default function nextConfig(phase: string): NextConfig {
  const dev = phase === PHASE_DEVELOPMENT_SERVER;
  return {
    trailingSlash: true,
    ...(dev
      ? {
          rewrites: async () => [
            { source: "/api/:path*", destination: `${FLASK_DEV_ORIGIN}/api/:path*` },
          ],
        }
      : { output: "export" }),
  };
}
