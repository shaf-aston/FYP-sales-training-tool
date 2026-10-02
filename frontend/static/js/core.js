let isTyping = false,
  userTurnIndex = 0,
  sessionId = null;

// Persist/restore session across refresh/navigation (server still enforces idle TTL).
const SESSION_STORAGE_KEY = "salesRoleplaySessionId";

// Read the saved session id so a refresh can reconnect to the same chat.
function getStoredSessionId() {
  try {
    const sid = localStorage.getItem(SESSION_STORAGE_KEY);
    return typeof sid === "string" && sid.trim() ? sid.trim() : null;
  } catch (_) {
    return null;
  }
}

// Save the active session id after the server creates or restores it.
function storeSessionId(sessionIdValue) {
  try {
    if (typeof sessionIdValue === "string" && sessionIdValue.trim()) {
      localStorage.setItem(SESSION_STORAGE_KEY, sessionIdValue.trim());
    }
  } catch (_) {}
}

// Remove the saved session id when a session is reset or expires.
function clearStoredSessionId() {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY);
  } catch (_) {}
}
// Module-level state to avoid circular DOM reads
let _currentStage = "intent";
let _currentStrategy = "-";
let _loadedStagesForStrategy = null; // tracks which strategy the stage list was last loaded for
let _editInProgress = false;
let _prospectMode = false;
let _prospectSessionId = null;
let _prospectDifficulty = "medium";
let _prospectProductType = "default";
let _prospectMaxTurns = null;
let _prospectScoringEnabled = true;
let _prospectFeedbackStyle = "coaching";
let _prospectSettings = {
  showHints: true,
  evalDisplay: "inline",
};
let _flowControlsEnabled = false;
let _sidebarTab = localStorage.getItem("sidebarTab") || "session";
let _lastTrainingHintToast = "";
let _sessionRecoveryInProgress = false;

const STRATEGY_META = {
  "-": {
    label: "Not started",
    note: "Begin the conversation to start tracking the flow.",
  },
  intent: {
    label: "INTENT",
    note: "FSM start state before strategy selection is resolved.",
  },
  consultative: {
    label: "CONSULTATIVE",
    note: "FSM consultative path: INTENT -> LOGICAL -> EMOTIONAL -> PITCH -> OBJECTION -> OUTCOME.",
  },
  transactional: {
    label: "TRANSACTIONAL",
    note: "FSM transactional path: INTENT -> PITCH -> NEGOTIATION -> OBJECTION -> OUTCOME.",
  },
  "prospect mode": {
    label: "Prospect practice",
    note: "You are in roleplay mode with a live buyer persona.",
  },
};

const FLOW_STAGE_META = {
  intent: {
    label: "INTENT",
    note: "Confirm user intent before advancing or switching strategy.",
  },
  logical: {
    label: "LOGICAL",
    note: "Surface doubt and clarify the user's current problem.",
  },
  emotional: {
    label: "EMOTIONAL",
    note: "Surface stakes, consequences, and motivation to change.",
  },
  pitch: {
    label: "PITCH",
    note: "Present the offer only when the FSM has reached pitch.",
  },
  negotiation: {
    label: "NEGOTIATION",
    note: "Resolve terms before objection handling in the transactional flow.",
  },
  objection: {
    label: "OBJECTION",
    note: "Handle the current objection without leaving the FSM path.",
  },
  outcome: {
    label: "OUTCOME",
    note: "Confirm commitment, walk-away, or final session outcome.",
  },
  default: {
    label: "Not started",
    note: "Begin the conversation to start tracking the flow.",
  },
};

const FLOW_STAGE_ORDER = {
  consultative: [
    "intent",
    "logical",
    "emotional",
    "pitch",
    "objection",
    "outcome",
  ],
  transactional: ["intent", "pitch", "objection", "outcome"],
  intent: ["intent"],
};

const _serverEnv = document.getElementById("server-env")?.dataset || {};
if (_serverEnv.flowControlsEnabled === "true") {
  _flowControlsEnabled = true;
}

try {
  const savedProspectSettings = JSON.parse(
    localStorage.getItem("prospectSettings") || "null",
  );
  if (savedProspectSettings && typeof savedProspectSettings === "object") {
    if (typeof savedProspectSettings.showHints === "boolean") {
      _prospectSettings.showHints = savedProspectSettings.showHints;
    }
    if (
      typeof savedProspectSettings.evalDisplay === "string" &&
      ["inline", "modal", "panel"].includes(savedProspectSettings.evalDisplay)
    ) {
      _prospectSettings.evalDisplay = savedProspectSettings.evalDisplay;
    }
  }
} catch (e) {
  console.warn("prospect settings restore failed:", e);
}

// Small session state accessors used across the UI.
function getSessionId() {
  return sessionId;
}

function hasProspectContext() {
  return (
    _prospectMode || isDedicatedProspectPage() || Boolean(_prospectSessionId)
  );
}

function shouldShowAutoCoachHints() {
  return _prospectMode || isDedicatedProspectPage();
}

// If server reports session loss, clear client state and re-init once.
function handleServerSessionError(data, { notify = true } = {}) {
  if (!data) return false;
  const errorText = String(data.error || "").toLowerCase();
  const isSessionExpired =
    data.code === "SESSION_EXPIRED" ||
    errorText.includes("session not found") ||
    errorText.includes("no active") ||
    errorText.includes("session expired");

  if (!isSessionExpired) return false;

  if (_sessionRecoveryInProgress) {
    return true;
  }

  _sessionRecoveryInProgress = true;

  // Check for error code first (reliable), then fallback to error message matching
  console.warn("Server lost session memory. Re-initializing...");
  clearStoredHistory();
  sessionId = null;
  clearStoredSessionId();
  if (notify) {
    showToast("Session expired - reconnecting...", "info");
  }
  initChatbot();
  return true;
}

// Toast Notifications
function showToast(message, type = "info") {
  // Remove existing toast if any
  const existing = document.querySelector(".toast-notification");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = `toast-notification toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  // Auto-remove after 4 seconds
  setTimeout(() => {
    toast.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function buildSessionHeaders(extraHeaders = {}) {
  const sid = getSessionId();
  if (!sid) return { ...extraHeaders };
  return { ...extraHeaders, "X-Session-ID": sid };
}

async function postSessionJson(url, body) {
  const sid = getSessionId();
  if (!sid) throw new Error("No active session");

  const response = await fetch(url, {
    method: "POST",
    headers: buildSessionHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));

  // Handle session errors consistently across flow-control requests.
  if (response.status === 404 || response.status === 400) {
    if (handleServerSessionError(data, { notify: true })) {
      throw new Error(data.error || "Session expired - please try again");
    }
  }

  if (!response.ok || !data.success) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

/* ---------------------------------------------------------------------------
 * Dialogs.
 * Every window that opens on top of the page goes through here, so Escape,
 * focus and the screen-reader attributes are defined once instead of being
 * re-remembered (and forgotten) per overlay.
 * ------------------------------------------------------------------------- */

const FOCUSABLE =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

let _dialogOpener = null;

function openDialog(overlay, card, labelId) {
  /* Announce it as a dialog. Without these a screen reader reads the overlay as
     ordinary page text and never says the learner has entered a window. */
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");
  if (labelId && card.querySelector("#" + labelId)) {
    card.setAttribute("aria-labelledby", labelId);
  }
  if (!card.hasAttribute("tabindex")) card.setAttribute("tabindex", "-1");

  overlay.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      closeDialog(overlay);
    } else if (event.key === "Tab") {
      trapTab(event, card);
    }
  });

  _dialogOpener = document.activeElement;
  document.body.appendChild(overlay);
  (card.querySelector(FOCUSABLE) || card).focus();
}

function trapTab(event, card) {
  /* Keeps Tab inside the window. Without it Tab walks onto the page behind,
     where the learner cannot see what is focused. */
  const items = [...card.querySelectorAll(FOCUSABLE)].filter(
    (el) => el.offsetParent !== null,
  );
  if (!items.length) return;

  const first = items[0];
  const last = items[items.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function closeDialog(overlay) {
  if (!overlay) return;
  overlay.remove();
  /* Put focus back where it came from, so keyboard users are not dumped at the
     top of the page after closing. */
  if (_dialogOpener && document.contains(_dialogOpener)) _dialogOpener.focus();
  _dialogOpener = null;
}
