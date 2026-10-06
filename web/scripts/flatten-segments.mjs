// Runs after `next build`. Next 16's static export writes nested-route prefetch files as
// folders (practice/__next.practice/sell/__PAGE__.txt) but the browser asks for one dotted
// name (practice/__next.practice.sell.__PAGE__.txt). Without a copy at the dotted name every
// prefetch 404s and links fall back to full page loads. Static hosts (Flask, Vercel) both need it.
import { cpSync, readdirSync, statSync } from "node:fs";
import { join, relative, sep } from "node:path";

const OUT = new URL("../out", import.meta.url).pathname;

function files(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? files(path) : [path];
  });
}

let copied = 0;
for (const routeDir of new Set([OUT, ...files(OUT).map((f) => f.slice(0, f.lastIndexOf(sep)))])) {
  for (const name of readdirSync(routeDir)) {
    const segDir = join(routeDir, name);
    if (!name.startsWith("__next.") || !statSync(segDir).isDirectory()) continue;
    for (const file of files(segDir)) {
      const dotted = `${name}.${relative(segDir, file).split(sep).join(".")}`;
      cpSync(file, join(routeDir, dotted));
      copied++;
    }
  }
}
console.log(`flatten-segments: ${copied} prefetch file(s) copied to dotted names`);
