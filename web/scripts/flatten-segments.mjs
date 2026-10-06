// Runs after `next build`. On Windows, Next 16.3's static export builds prefetch file names
// from `path.relative` (backslashes) but `convertSegmentPathToStaticExportFilename` only turns
// `/` into `.`, so it writes folders (practice/__next.practice/sell/__PAGE__.txt) where the
// browser asks for one dotted name (practice/__next.practice.sell.__PAGE__.txt) → every prefetch
// 404s. This moves each file to its dotted name. Linux/macOS output is already flat: no-op there.
import { readdirSync, renameSync, rmSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const OUT = fileURLToPath(new URL("../out", import.meta.url));
const ls = (dir) => readdirSync(dir, { recursive: true, withFileTypes: true });

let moved = 0;
for (const seg of ls(OUT)) {
  if (!seg.isDirectory() || !seg.name.startsWith("__next.")) continue;
  const segDir = join(seg.parentPath, seg.name);
  for (const f of ls(segDir)) {
    if (!f.isFile()) continue;
    const rel = relative(segDir, join(f.parentPath, f.name));
    renameSync(join(segDir, rel), join(seg.parentPath, `${seg.name}.${rel.split(sep).join(".")}`));
    moved++;
  }
  rmSync(segDir, { recursive: true });
}
console.log(`flatten-segments: ${moved} prefetch file(s) moved to dotted names`);
