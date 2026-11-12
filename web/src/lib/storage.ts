// Safe web storage access: private windows and blocked storage throw, so every call is guarded.
// "local" (the default) lasts across visits; "session" lasts while the tab is open (reloads and Back included).

type Area = "local" | "session";
const area = (where: Area) => (where === "session" ? sessionStorage : localStorage);

export function readString(key: string, where: Area = "local"): string | null {
  try {
    return area(where).getItem(key);
  } catch {
    return null;
  }
}

export function writeString(key: string, value: string | null, where: Area = "local"): void {
  try {
    if (value === null) area(where).removeItem(key);
    else area(where).setItem(key, value);
  } catch {
    /* storage unavailable: keep working without persistence */
  }
}

/** False in private windows or when site data is blocked. */
export function storageAvailable(): boolean {
  try {
    const probe = "__probe__";
    localStorage.setItem(probe, probe);
    localStorage.removeItem(probe);
    return true;
  } catch {
    return false;
  }
}
