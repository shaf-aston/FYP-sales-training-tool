// Small helpers for files the learner drops or chooses (call transcripts, recordings, SOPs).

/** ".VTT" in "Call.VTT" -> ".vtt"; "" when the name has no extension. */
export const extOf = (name: string) => (name.includes(".") ? name.slice(name.lastIndexOf(".")).toLowerCase() : "");

/** True when the file's extension is one of `exts` (each with its dot, lower case). */
export const hasExt = (file: File, exts: readonly string[]) => exts.includes(extOf(file.name));

/** [".txt", ".vtt", ".srt"] -> ".txt, .vtt or .srt" */
export const listOf = (items: readonly string[]) =>
  items.length > 1 ? `${items.slice(0, -1).join(", ")} or ${items[items.length - 1]}` : (items[0] ?? "");

/** 25_000_000 -> "25 MB" */
export const megabytes = (bytes: number) => `${Math.round(bytes / 1_000_000)} MB`;

/** A text file's contents, read in the browser. */
export function readText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}
