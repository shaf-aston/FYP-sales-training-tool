// Hand the learner a file made in the browser (no server round trip for the file itself).

/** Saves `data` as a pretty-printed JSON file called `filename`. */
export function saveJson(filename: string, data: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  // The click has started the download; the URL is no longer needed.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
