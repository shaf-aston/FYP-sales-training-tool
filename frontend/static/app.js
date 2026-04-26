let isTyping = false,
  userTurnIndex = 0,
  sessionId = null;

// Persist/restore session across refresh/navigation (server still enforces idle TTL).
const SESSION_STORAGE_KEY = "salesRoleplaySessionId";

function getStoredSessionId() {
  try {
    const sid = localStorage.getItem(SESSION_STORAGE_KEY);
    return typeof sid === "string" && sid.trim() ? sid.trim() : null;
  } catch (_) {
    return null;
  }
}

function storeSessionId(sid) {
  try {
    if (typeof sid === "string" && sid.trim()) {
      localStorage.setItem(SESSION_STORAGE_KEY, sid.trim());
    }
  } catch (_) {}
}

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
let _prospectSettings = {
  showHints: true,
  evalDisplay: "inline",
};
let _flowControlsEnabled = false;

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

// Voice Mode State
let handsFreeMode = false;
let currentTtsAudio = null;
let ttsPlaybackSpeed = parseInt(
  localStorage.getItem("ttsPlaybackSpeed") || "0",
); // Range: -50 to +50 percent, default 0 is normal speed
let shouldAutoSendAfterSilence =
  localStorage.getItem("autoSendDictation") !== "false";
const VOICE_SILENCE_DELAY_MS = 500; // Wait for 0.5 seconds of silence before auto-send
const TTS_RESUME_WATCHDOG_MS = 15000;
let voiceSilenceTimer = null;
let ttsResumeWatchdogTimer = null;
let ttsPlaybackGeneration = 0;
let ttsPlaybackPending = false;
let _handsFreeRestartAttempts = 0;

// Settings Toggles
function toggleAutoSend() {
  const checkbox = document.getElementById("autoSendDictationToggle");
  shouldAutoSendAfterSilence = checkbox.checked;
  localStorage.setItem("autoSendDictation", shouldAutoSendAfterSilence);
  showToast(
    `Auto-send after pause ${shouldAutoSendAfterSilence ? "ON" : "OFF"}`,
  );
}

function updateTtsSpeed(value) {
  ttsPlaybackSpeed = parseInt(value);
  const speedValue = document.getElementById("ttsSpeedValue");
  const speedPercent = document.getElementById("ttsSpeedPercent");

  // Update label text based on speed
  if (ttsPlaybackSpeed < 0) {
    speedValue.textContent = `Slower (${ttsPlaybackSpeed}%)`;
  } else if (ttsPlaybackSpeed > 0) {
    speedValue.textContent = `Faster (+${ttsPlaybackSpeed}%)`;
  } else {
    speedValue.textContent = "Normal";
  }

  speedPercent.textContent = `${ttsPlaybackSpeed > 0 ? "+" : ""}${ttsPlaybackSpeed}%`;
  localStorage.setItem("ttsPlaybackSpeed", ttsPlaybackSpeed);
}

// Initialize TTS speed slider from localStorage
function initTtsSpeedControl() {
  const slider = document.getElementById("ttsSpeedSlider");
  if (slider) {
    slider.value = ttsPlaybackSpeed;
    updateTtsSpeed(ttsPlaybackSpeed);
  }
}

// Training Style
let trainingStyle = localStorage.getItem("trainingStyle") || "tactical";

function changeTrainingStyle(val) {
  trainingStyle = val;
  localStorage.setItem("trainingStyle", val);
}

// Session Managementâ”€â”€â”€â”€
function getSessionId() {
  return sessionId;
}

function hasProspectContext() {
  return (
    _prospectMode ||
    isDedicatedProspectPage() ||
    Boolean(_prospectSessionId)
  );
}

// In-memory history only. Sessions are intentionally not restored after refresh.
// Stored as [{role:"user"|"assistant", content:str}]
let _cachedHistory = [];

function trimHistoryCache() {
  const MAX_HISTORY = 100;
  if (_cachedHistory.length > MAX_HISTORY) {
    _cachedHistory = _cachedHistory.slice(-MAX_HISTORY);
  }
}

function clearStoredHistory() {
  _cachedHistory = [];
  _loadedStagesForStrategy = null;
}

function normalizeConversationHistory(history) {
  if (!Array.isArray(history)) return [];

  // Skip any leading assistant messages (e.g. the opening greeting stored before
  // the first user turn). The loop below expects strict user/assistant pairs.
  let start = 0;
  while (start < history.length && history[start]?.role !== "user") {
    start++;
  }

  const normalized = [];
  for (let idx = start; idx + 1 < history.length; idx += 2) {
    const userEntry = history[idx];
    const botEntry = history[idx + 1];

    if (
      !userEntry ||
      !botEntry ||
      userEntry.role !== "user" ||
      botEntry.role !== "assistant" ||
      typeof userEntry.content !== "string" ||
      typeof botEntry.content !== "string"
    ) {
      break;
    }

    normalized.push(
      { role: "user", content: userEntry.content },
      { role: "assistant", content: botEntry.content },
    );
  }

  return normalized;
}

function renderHistory(history) {
  const container = document.getElementById("chatContainer");
  container.innerHTML = "";
  userTurnIndex = 0;
  history.forEach((m) =>
    renderMessage(m.content, m.role === "user" ? "user" : "bot"),
  );
}

function replaceConversationHistory(history) {
  _cachedHistory = normalizeConversationHistory(history);
  trimHistoryCache();
  const container = document.getElementById("chatContainer");
  container.innerHTML = "";
  userTurnIndex = 0;
  if (Array.isArray(history)) {
    history.forEach((m) => renderMessage(m.content, m.role === "user" ? "user" : "bot"));
  }
}

function resetConversationState() {
  clearStoredHistory();
  sessionId = null;
  _currentStage = "intent";
  _currentStrategy = "-";
  updateStage("intent");
  updateStrategy("-");
  syncModeChrome();
}

// NOTE: The prospect product dropdown (#prospectProductSelect) is populated
// server-side by Flask/Jinja in index.html from backend.app._prospect_product_options().
// No JS fetch is needed -- options are already in the HTML on page load.

function syncKnowledgeBaseLink() {
  const link = document.getElementById("knowledgeBaseLink");
  if (!link) return;

  const isProspectContext = isDedicatedProspectPage() || _prospectMode;

  link.href = isProspectContext ? "/knowledge?mode=prospect" : "/knowledge";
  link.textContent = isProspectContext ? "Prospect Knowledge" : "Knowledge";
}

function isDedicatedProspectPage() {
  return typeof PAGE_MODE !== "undefined" && PAGE_MODE === "prospect";
}

function syncModeChrome() {
  const isProspectContext = isDedicatedProspectPage() || _prospectMode;
  const flowControls = document.getElementById("flowControls");
  const showFlowControls = _flowControlsEnabled && !isProspectContext;

  if (flowControls) {
    flowControls.style.display = showFlowControls ? "" : "none";
  }

  if (!showFlowControls) {
    populateStageSelects([]);
    setFlowControlsEnabled(false);
    syncStrategySelectors("");
    return;
  }

  syncStrategySelectors(_currentStrategy);
  if (getSessionId()) {
    loadStageOptions();
  } else {
    populateStageSelects([]);
    setFlowControlsEnabled(false);
  }
}

// Session Expiration Handler
function handleSessionExpired() {
  // Clear all stored data
  clearStoredHistory();
  sessionId = null;
  clearStoredSessionId();

  // Clear the chat container
  const container = document.getElementById("chatContainer");
  container.innerHTML = "";

  // Add a notice
  const notice = document.createElement("div");
  notice.className = "edit-divider";
  notice.textContent = "Session expired - conversation has been reset";
  notice.style.color = "#d4a373";
  notice.style.marginBottom = "12px";
  container.appendChild(notice);

  // Reinitialize the chatbot
  initChatbot();
}

// If server reports session loss, clear client state and re-init
function handleServerSessionError(data) {
  if (!data) return false;
  // Check for error code first (reliable), then fallback to error message matching
  if (
    data.code === "SESSION_EXPIRED" ||
    (data.error &&
      (data.error.toLowerCase().includes("session") ||
        data.error.toLowerCase().includes("no active")))
  ) {
    console.warn("Server lost session memory. Re-initializing...");
    clearStoredHistory();
    sessionId = null;
    initChatbot();
    return true;
  }
  return false;
}

function isProspectSessionExpired(data) {
  if (!data) return false;
  if (data.code === "SESSION_EXPIRED") return true;
  if (!data.error) return false;

  const errorText = String(data.error).toLowerCase();
  return (
    errorText.includes("prospect session") ||
    errorText.includes("no active prospect session")
  );
}

function clearProspectSessionState() {
  _prospectMode = false;
  _prospectSessionId = null;
  clearProspectEvaluationPanel();
  syncKnowledgeBaseLink();
  syncModeChrome();
}

function clearProspectEvaluationPanel() {
  const panel = document.getElementById("prospectEvalPanelContent");
  if (panel) panel.remove();
}

function normalizeProspectConversationHistory(data) {
  if (
    Array.isArray(data?.conversation_history) &&
    data.conversation_history.length
  ) {
    return data.conversation_history;
  }

  if (typeof data?.message === "string" && data.message.trim()) {
    return [{ role: "assistant", content: data.message }];
  }

  return [];
}

function handleProspectSessionError(data) {
  if (!isProspectSessionExpired(data)) return false;

  console.warn("Prospect session expired or missing on the server.");
  clearProspectSessionState();
  document.getElementById("chatContainer").innerHTML = "";
  userTurnIndex = 0;
  document.getElementById("sendBtn").disabled = false;
  openProspectSetup();
  showToast("Prospect session expired. Start a new one.", "error");
  return true;
}

async function restoreProspectSession(sessionId) {
  const response = await fetch("/api/prospect/state", {
    headers: { "X-Session-ID": sessionId },
  });
  const data = await response.json().catch(() => ({}));

  if (!response.ok || !data.success || !data.persona) {
    throw new Error(data.error || "Invalid prospect session state");
  }

  applyProspectSessionFromServer(sessionId, {
    ...data,
    conversation_history: normalizeProspectConversationHistory(data),
  });
}

// Text-to-Speech Functions
const tts = {
  speak: (t) => playAssistantTts(t).then(() => true),
  stop: () => stopTtsPlayback(),
  isSpeaking: () =>
    ttsPlaybackPending ||
    Boolean(currentTtsAudio) ||
    ("speechSynthesis" in window && speechSynthesis.speaking),
};

// Toast Notifications
function showToast(message, type = "info") {
  // Remove existing toast if any
  const existing = document.querySelector(".toast-notification");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.className = `toast-notification toast-${type}`;
  toast.textContent = message;
  toast.style.cssText = `
    position: fixed;
    bottom: 100px;
    left: 50%;
    transform: translateX(-50%);
    padding: 12px 24px;
    border-radius: 8px;
    background: ${type === "error" ? "#dc2626" : type === "success" ? "#16a34a" : "#2563eb"};
    color: white;
    font-size: 14px;
    z-index: 10000;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    animation: toastIn 0.3s ease;
  `;
  document.body.appendChild(toast);

  // Auto-remove after 4 seconds
  setTimeout(() => {
    toast.style.animation = "toastOut 0.3s ease forwards";
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

function clearVoiceSilenceTimer() {
  if (!voiceSilenceTimer) return;
  clearTimeout(voiceSilenceTimer);
  voiceSilenceTimer = null;
}

function scheduleVoiceAutoSend(inputEl) {
  if (!shouldAutoSendAfterSilence) return;

  clearVoiceSilenceTimer();
  voiceSilenceTimer = setTimeout(() => {
    voiceSilenceTimer = null;
    if (inputEl.value.trim()) sendMessage();
  }, VOICE_SILENCE_DELAY_MS);
}

function _setDictationPreview(text) {
  const el = document.getElementById("dictationPreview");
  if (!el) return;
  if (text && text.trim()) {
    el.textContent = text;
    el.style.display = "";
  } else {
    el.textContent = "";
    el.style.display = "none";
  }
}

function _showTTSBanner(on) {
  const el = document.getElementById("ttsSpeakingBanner");
  if (el) el.style.display = on ? "" : "none";
}

function parsePunctuation(text) {
  return text
    .replace(/ period /g, ". ")
    .replace(/ comma /g, ", ")
    .replace(/ new line /g, "\n");
}

const _voiceStagePattern =
  /\b(?:jump|go|move|switch)\s+(?:to\s+)?(?:the\s+)?(?:stage\s+)?(intent|logical|emotional|pitch|objection)\b/i;
const _voiceStrategyPattern =
  /\b(?:switch|set)\s+(?:strategy\s+)?(?:to\s+)?(intent|consultative|transactional)\b/i;

function parseFlowVoiceCommand(rawText) {
  const text = String(rawText || "")
    .trim()
    .toLowerCase();
  if (!text) return null;

  let match = text.match(_voiceStrategyPattern);
  if (match) {
    return { type: "strategy", value: match[1] };
  }

  match = text.match(_voiceStagePattern);
  if (match) {
    return { type: "stage", value: match[1] };
  }

  return null;
}

async function requestStageJump(stage) {
  if (!_flowControlsEnabled) {
    throw new Error("Flow controls are disabled");
  }
  return postSessionJson("/api/stage", { stage });
}

async function requestStrategySwitch(strategy) {
  if (!_flowControlsEnabled) {
    throw new Error("Flow controls are disabled");
  }
  return postSessionJson("/api/strategy", { strategy });
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
  if (!response.ok || !data.success) {
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function setFlowControlsEnabled(enabled) {
  [
    "stageSelect",
    "stageSelectMain",
    "jumpStageBtn",
    "jumpStageMainBtn",
    "strategySelectMain",
    "switchStrategyBtn",
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.disabled = !enabled;
  });
}

function populateStageSelects(stages, selectedStage = "") {
  const normalizedSelected = String(selectedStage || "")
    .trim()
    .toLowerCase();

  ["stageSelect", "stageSelectMain"].forEach((id) => {
    const select = document.getElementById(id);
    if (!select) return;

    select.innerHTML = "";

    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.textContent = stages.length
      ? "Select stage..."
      : "No stages available";
    select.appendChild(placeholder);

    stages.forEach((stage) => {
      const normalizedStage = String(stage || "")
        .trim()
        .toLowerCase();
      if (!normalizedStage) return;

      const option = document.createElement("option");
      option.value = normalizedStage;
      option.textContent = normalizedStage.toUpperCase();
      select.appendChild(option);
    });

    select.value = stages.includes(normalizedSelected)
      ? normalizedSelected
      : "";
    select.disabled = stages.length === 0;
  });
}

async function loadStageOptions() {
  if (!_flowControlsEnabled) {
    populateStageSelects([]);
    setFlowControlsEnabled(false);
    return [];
  }

  const sid = getSessionId();
  if (!sid) {
    populateStageSelects([]);
    setFlowControlsEnabled(false);
    return [];
  }

  try {
    const response = await fetch("/api/stages", {
      headers: buildSessionHeaders(),
    });
    const data = await response.json().catch(() => ({}));

    if (!response.ok || !data.success) {
      throw new Error(data.error || "Failed to load stages");
    }

    const stages = Array.isArray(data.stages)
      ? data.stages
          .map((stage) =>
            String(stage || "")
              .trim()
              .toLowerCase(),
          )
          .filter(Boolean)
      : [];

    populateStageSelects(stages, _currentStage);
    setFlowControlsEnabled(true);
    return stages;
  } catch (error) {
    console.warn("Stage options unavailable:", error);
    populateStageSelects([]);
    setFlowControlsEnabled(false);
    return [];
  }
}

async function jumpStage(selectId = "stageSelect") {
  const select =
    document.getElementById(selectId) || document.getElementById("stageSelect");
  const stage = String(select?.value || "")
    .trim()
    .toLowerCase();

  if (!stage) {
    showToast("Pick a stage first", "info");
    return;
  }

  try {
    const data = await requestStageJump(stage);
    updateSessionUI(data);
    await loadStageOptions();
    showToast(`Jumped to ${stage.toUpperCase()}`, "success");
  } catch (error) {
    showToast(error.message || "Stage jump failed", "error");
  }
}

async function switchStrategy(selectId = "strategySelectMain") {
  const select =
    document.getElementById(selectId) ||
    document.getElementById("strategySelectMain");
  const strategy = String(select?.value || "")
    .trim()
    .toLowerCase();

  if (!strategy) {
    showToast("Pick a strategy first", "info");
    return;
  }

  try {
    const data = await requestStrategySwitch(strategy);
    updateSessionUI(data);
    await loadStageOptions();
    showToast(`Strategy set to ${strategy.toUpperCase()}`, "success");
  } catch (error) {
    syncStrategySelectors(_currentStrategy);
    showToast(error.message || "Strategy switch failed", "error");
  }
}

async function executeFlowVoiceCommand(command) {
  if (!command) return false;

  try {
    if (command.type === "stage") {
      const d = await requestStageJump(command.value);
      updateSessionUI(d);
      showToast("Voice: jumped -> " + command.value.toUpperCase(), "info");
      return true;
    }

    if (command.type === "strategy") {
      const d = await requestStrategySwitch(command.value);
      updateSessionUI(d);
      showToast("Voice: strategy -> " + command.value.toUpperCase(), "info");
      return true;
    }
  } catch (e) {
    showToast("Voice command error: " + e, "error");
  }

  return false;
}

// Message Rendering
function parseMarkdown(line) {
  if (
    typeof marked !== "undefined" &&
    typeof marked.parseInline === "function"
  ) {
    try {
      return marked.parseInline(line);
    } catch (e) {
      console.warn("Marked parse error:", e);
    }
  }
  return line
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^(\d+)\.\s/, "<strong>$1.</strong> ");
}

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function createMessageElement(text, sender, msgIdx, metrics = null) {
  const msg = document.createElement("div");
  msg.className = `message ${sender} message-enter`;

  if (msgIdx !== null && msgIdx !== undefined) {
    msg.setAttribute("data-msg-idx", msgIdx);
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  const safeText = text || "";

  if (sender === "bot" && typeof marked !== "undefined") {
    // Use marked.js for bot messages to support full markdown (lists, bold, etc)
    bubble.innerHTML = DOMPurify.sanitize(marked.parse(safeText));
  } else {
    // Fallback / User messages: preserve newlines
    bubble.innerHTML = safeText
      .split("\n")
      .map((l) => {
        const s = document.createElement("span");
        if (sender === "bot") {
          s.innerHTML = DOMPurify.sanitize(parseMarkdown(l));
        } else {
          s.textContent = l;
        }
        return s.outerHTML;
      })
      .join("<br>");
  }

  const actions = document.createElement("div");
  actions.className = "message-actions";

  if (sender === "bot") {
    const btn = Object.assign(document.createElement("button"), {
      className: "tts-btn",
      innerHTML: "🔊",
      title: "Read aloud",
    });
    btn.onclick = () => {
      if (tts.isSpeaking()) {
        tts.stop();
        btn.classList.remove("speaking");
      } else {
        playAssistantTts(text, {
          onStart: () => btn.classList.add("speaking"),
        });
      }
    };
    actions.appendChild(btn);
  } else {
    const btn = Object.assign(document.createElement("button"), {
      className: "edit-btn",
      innerHTML: "âœï¸ Edit",
    });
    btn.textContent = "Edit";
    if (_prospectMode) {
      msg.appendChild(bubble);
      return msg;
    }
    btn.onclick = () => editMessage(msgIdx, text, msg);
    actions.appendChild(btn);
  }

  msg.appendChild(bubble);
  if (actions.childElementCount > 0) {
    msg.appendChild(actions);
  }

  if (metrics && sender === "bot") {
    const metricsDiv = document.createElement("div");
    metricsDiv.className = "message-metrics";
    let t = `${metrics.latency_ms.toFixed(1)}ms`;
    if (metrics.provider) t += ` • ${metrics.provider}`;
    if (metrics.input_length || metrics.output_length)
      t += ` • ${metrics.input_length}→${metrics.output_length}`;
    t = `${metrics.latency_ms.toFixed(1)}ms`;
    if (metrics.provider) t += ` - ${metrics.provider}`;
    if (metrics.input_length || metrics.output_length) {
      t += ` - ${metrics.input_length}->${metrics.output_length}`;
    }
    metricsDiv.textContent = t;
    msg.appendChild(metricsDiv);
  }

  return msg;
}

// Inline Message Editing
// Clicking Edit replaces the bubble with an inline textarea.
// On Save: grey out everything from the edited message onward,
// insert a divider, then append the new branch below.
function editMessage(msgIdx, originalText, msgEl) {
  if (_editInProgress) {
    showToast("Finish the current edit first", "info");
    return;
  }
  _editInProgress = true;

  const container = document.getElementById("chatContainer");

  // Swap bubble for inline editor
  const bubble = msgEl.querySelector(".message-bubble");
  const actions = msgEl.querySelector(".message-actions");
  bubble.style.display = "none";
  actions.style.display = "none";

  const ta = document.createElement("textarea");
  ta.className = "inline-edit-box";
  ta.value = originalText;

  const btnRow = document.createElement("div");
  btnRow.className = "inline-edit-actions";

  const saveBtn = document.createElement("button");
  saveBtn.className = "inline-save-btn";
  saveBtn.textContent = "Save";

  const cancelBtn = document.createElement("button");
  cancelBtn.className = "inline-cancel-btn";
  cancelBtn.textContent = "Cancel";

  btnRow.append(saveBtn, cancelBtn);
  msgEl.append(ta, btnRow);
  ta.focus();

  cancelBtn.onclick = () => {
    _editInProgress = false;
    ta.remove();
    btnRow.remove();
    bubble.style.display = "";
    actions.style.display = "";
  };

  saveBtn.onclick = () => {
    const newText = ta.value.trim();
    if (!newText || newText === originalText) {
      _editInProgress = false;
      cancelBtn.click();
      return;
    }
    if (newText.length > 1000) {
      alert("Message too long (max 1000 characters)");
      return;
    }

    // Disable edit UI while waiting
    saveBtn.disabled = true;
    cancelBtn.disabled = true;
    ta.disabled = true;

    // Grey out from edited message to end of container
    const allMsgs = [...container.children];
    const startIdx = allMsgs.indexOf(msgEl);
    for (let i = startIdx; i < allMsgs.length; i++) {
      allMsgs[i].classList.add("historical");
      allMsgs[i].removeAttribute("data-msg-idx");
    }

    // Recompute userTurnIndex = active (non-historical) user msgs
    userTurnIndex = container.querySelectorAll(
      ".message.user:not(.historical)",
    ).length;

    fetch("/api/edit", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getSessionId(),
      },
      body: JSON.stringify({ index: msgIdx, message: newText }),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.success) {
          // Check if session expired using improved error detection
          if (handleServerSessionError(data)) {
            return;
          }

          // Undo greying
          allMsgs
            .slice(startIdx)
            .forEach((el) => el.classList.remove("historical"));
          userTurnIndex = container.querySelectorAll(
            ".message.user:not(.historical)",
          ).length;
          _editInProgress = false;
          ta.disabled = false;
          saveBtn.disabled = false;
          cancelBtn.disabled = false;
          showToast("Edit failed: " + (data.error || "Unknown error"), "error");
          return;
        }

        // Remove inline editor, restore hidden bubble (now historical)
        ta.remove();
        btnRow.remove();
        bubble.style.display = "";
        actions.style.display = "";

        // Insert visual divider
        const divider = document.createElement("div");
        divider.className = "edit-divider";
        divider.textContent = "Edited";
        container.appendChild(divider);

        // Append new branch: everything from edit point in returned history
        // data.history is the full new history; slice from msgIdx onward
        const newMsgs = data.history.slice(msgIdx);
        newMsgs.forEach((m, i) => {
          const role = m.role === "user" ? "user" : "bot";
          let metrics = null;
          if (i === newMsgs.length - 1 && role === "bot" && data.latency_ms) {
            metrics = {
              latency_ms: data.latency_ms,
              provider: data.provider || "",
              input_length: 0,
              output_length: 0,
            };
          }
          addMessage(m.content, role, metrics);
        });

        // Sync cached history with server truth
        _cachedHistory = data.history.map((m) => ({
          role: m.role,
          content: m.content,
        }));
        trimHistoryCache();
        _editInProgress = false;

        updateSessionUI(data);
      })
      .catch((e) => {
        rollbackEditUI(allMsgs, startIdx);
        userTurnIndex = container.querySelectorAll(
          ".message.user:not(.historical)",
        ).length;
        _editInProgress = false;
        ta.disabled = false;
        saveBtn.disabled = false;
        cancelBtn.disabled = false;
        showToast("Edit didn't go through -- try it again", "error");
      });
  };
}

// Initialization and Page Reload Restoration
function initChatbot() {
  const storedSid = getStoredSessionId();
  fetch("/api/init", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    // If the server still has the session in memory (within idle TTL),
    // this restores the conversation after refresh/navigation.
    body: JSON.stringify(storedSid ? { session_id: storedSid } : {}),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        showToast(data.error, "error");
        // Stored session might have expired server-side; clear and try fresh once.
        if (storedSid) {
          clearStoredSessionId();
          initChatbot();
        }
        return;
      }

      sessionId = data.session_id;
      storeSessionId(sessionId);
      userTurnIndex = 0;
      clearStoredHistory();

      // New sessions return a greeting in `message`.
      // Restored in-memory sessions return `message: null` and provide the greeting in `history`.
      if (typeof data.message === "string" && data.message.trim()) {
        addMessage(data.message, "bot");
      } else if (Array.isArray(data.history) && data.history.length) {
        replaceConversationHistory(data.history);
      }
      updateSessionUI(data);

      loadStageOptions();
      syncStrategySelectors(_currentStrategy);
    })
    .catch((error) => {
      showToast("Connection error - please refresh", "error");
    });
}

window.addEventListener("DOMContentLoaded", () => {
  const ta = document.getElementById("messageInput");
  ta.addEventListener("input", () => autoResizeTextarea(ta));
  speechRecognizer = new SpeechRecognizer();

  const autoSendCheckbox = document.getElementById("autoSendDictationToggle");
  if (autoSendCheckbox) {
    autoSendCheckbox.checked = shouldAutoSendAfterSilence;
  }

  // Init send-mode controls
  const styleSel = document.getElementById("trainingStyle");
  if (styleSel) styleSel.value = trainingStyle;

  // Prospect product dropdown is rendered server-side (see index.html).
  syncKnowledgeBaseLink();
  syncModeChrome();
  syncStrategySelectors(_currentStrategy);

  if (isDedicatedProspectPage()) {
    openProspectSetup();
  } else {
    initChatbot();
    // Restore training panel open state
    if (localStorage.getItem("trainingPanelOpen") === "true") {
      document.getElementById("trainingPanel").classList.add("open");
      document.querySelector(".container").classList.add("panel-open");
    }
  }
});

// renderMessage Function
// Render-only (no cache side effects). Used during history restore.
function renderMessage(text, sender) {
  const container = document.getElementById("chatContainer");
  let msgIdx = null;
  if (sender === "user") {
    msgIdx = userTurnIndex * 2;
    userTurnIndex += 1;
  }
  const el = createMessageElement(text, sender, msgIdx, null);
  container.appendChild(el);
  requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });
}

// addMessage Function
function addMessage(text, sender, metrics = null) {
  // Render to DOM first (without cache side effects)
  const container = document.getElementById("chatContainer");
  let msgIdx = null;
  if (sender === "user") {
    msgIdx = userTurnIndex * 2;
    userTurnIndex += 1;
  }

  const el = createMessageElement(text, sender, msgIdx, metrics);
  container.appendChild(el);
  requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });

  // Then update cache (unique to addMessage, not called during restore)
  if (sender === "user") {
    _cachedHistory.push({ role: "user", content: text });
  } else {
    // Cache all bot responses (including initial greeting)
    _cachedHistory.push({ role: "assistant", content: text });
  }
  trimHistoryCache();
}

function restorePendingInput(message) {
  const input = document.getElementById("messageInput");
  if (!input) return;
  if (!input.value.trim()) {
    input.value = message;
    autoResizeTextarea(input);
  }
  input.focus();
}

function rollbackOptimisticUserMessage(message) {
  const lastEntry = _cachedHistory[_cachedHistory.length - 1];
  if (lastEntry?.role === "user" && lastEntry.content === message) {
    replaceConversationHistory(_cachedHistory.slice(0, -1));
  } else {
    renderHistory(_cachedHistory);
  }
  restorePendingInput(message);
}

async function reconcileChatStateAfterFailedSend(message) {
  const sid = getSessionId();
  const optimisticLength = _cachedHistory.length;
  if (!sid) {
    rollbackOptimisticUserMessage(message);
    return "rolled-back";
  }

  try {
    const response = await fetch("/api/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sid }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.error || !Array.isArray(data.history)) {
      throw new Error(data.error || "Session reconcile failed");
    }

    replaceConversationHistory(data.history);
    updateSessionUI(data);

    if (_cachedHistory.length > optimisticLength) {
      return "server-accepted";
    }
    if (_cachedHistory.length < optimisticLength) {
      restorePendingInput(message);
      return "rolled-back";
    }
    return "reconciled";
  } catch (error) {
    rollbackOptimisticUserMessage(message);
    return "rolled-back";
  }
}

// sendMessage Function
async function sendMessage() {
  // Route to prospect mode if active
  if (_prospectMode) {
    sendProspectMessage();
    return;
  }

  const input = document.getElementById("messageInput");
  const message = input.value.trim();
  if (!message || isTyping) return;

  isTyping = true;
  document.getElementById("sendBtn").disabled = true;

  addMessage(message, "user");
  input.value = "";
  autoResizeTextarea(input);
  showTyping();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 25000);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": getSessionId(),
      },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    const data = await response.json().catch(() => ({}));
    hideTyping();

    if (!response.ok || data.error) {
      // Check if session expired using improved error detection
      if (handleServerSessionError(data)) return;

      await reconcileChatStateAfterFailedSend(message);
      showToast(data.error || "Message failed - try again", "error");
      return;
    }

    const metrics = {
      latency_ms: data.latency_ms || 0,
      provider: data.provider || "",
      input_length: data.metrics?.input_length || 0,
      output_length: data.metrics?.output_length || 0,
    };
    addMessage(data.message, "bot", metrics);
    updateSessionUI(data);
    if (handsFreeMode) playAssistantTts(data.message);
  } catch (error) {
    clearTimeout(timeoutId);
    hideTyping();
    const recovery = await reconcileChatStateAfterFailedSend(message);
    if (recovery === "server-accepted") {
      showToast("Recovered the latest server state", "info");
      return;
    }
    const msg =
      error.name === "AbortError"
        ? "Response timed out - give it another shot"
        : "Connection dropped - try once more";
    showToast(msg, "error");
  }
}

// Typing Indicator
function showTyping() {
  isTyping = true;
  const container = document.getElementById("chatContainer");
  const typingDiv = document.createElement("div");
  typingDiv.className = "message bot";
  typingDiv.id = "typingIndicator";
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  const indicator = document.createElement("div");
  indicator.className = "typing-indicator";
  indicator.setAttribute("role", "status");
  indicator.setAttribute("aria-label", "Assistant is typing");
  indicator.innerHTML = "<span></span><span></span><span></span>";
  bubble.appendChild(indicator);
  typingDiv.appendChild(bubble);
  container.appendChild(typingDiv);
  container.scrollTop = container.scrollHeight;
  document.getElementById("sendBtn").disabled = true;
}

function hideTyping() {
  isTyping = false;
  document.getElementById("typingIndicator")?.remove();
  document.getElementById("sendBtn").disabled = false;
}

// Badge Helper Functions
function updateStage(stage) {
  _currentStage = stage;
  document.getElementById("stageBadge").textContent = stage.toUpperCase();
}

function syncStrategySelectors(strategy) {
  const normalized = String(strategy || "")
    .trim()
    .toLowerCase();
  const known = new Set(["intent", "consultative", "transactional"]);
  ["strategySelectMain"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = known.has(normalized) ? normalized : "";
  });
}

function updateStrategy(strategy) {
  _currentStrategy = strategy;
  document.getElementById("strategyBadge").textContent = strategy.toUpperCase();
  syncStrategySelectors(strategy);
}

// Consolidated UI update helper
function updateSessionUI(data) {
  if (data.stage) updateStage(data.stage);
  if (data.strategy) {
    const strategyChanged = data.strategy !== _currentStrategy;
    updateStrategy(data.strategy);
    if (
      document.getElementById("stageSelect") ||
      document.getElementById("stageSelectMain")
    ) {
      if (strategyChanged || _loadedStagesForStrategy === null) {
        _loadedStagesForStrategy = data.strategy;
        loadStageOptions();
      } else {
        // Strategy unchanged - just sync the selected value without an API call
        populateStageSelects(
          [...(document.getElementById("stageSelect")?.options ?? [])]
            .map((o) => o.value)
            .filter(Boolean),
          data.stage || _currentStage,
        );
      }
    }
  } else if (data.stage) {
    // Stage changed but strategy didn't come back - sync select value only
    populateStageSelects(
      [...(document.getElementById("stageSelect")?.options ?? [])]
        .map((o) => o.value)
        .filter(Boolean),
      data.stage,
    );
  }
  if (data.training) updateTrainingPanel(data.training);
}
// Edit rollback helper
function rollbackEditUI(allMsgs, startIdx) {
  allMsgs.slice(startIdx).forEach((el) => el.classList.remove("historical"));
}

// Tools dropdown moved to Sidebar

// Exclusive Panel Management
function closeAllPanels() {
  const container = document.querySelector(".container");
  ["trainingPanel", "quizPanel", "prospectPanel"].forEach((panelId) => {
    document.getElementById(panelId)?.classList.remove("open");
  });
  container?.classList.remove(
    "panel-open",
    "quiz-panel-open",
    "prospect-panel-open",
  );
}

function toggleTrainingPanel() {
  const panel = document.getElementById("trainingPanel");
  const container = document.querySelector(".container");
  const willOpen = !panel.classList.contains("open");
  if (willOpen) {
    closeAllPanels();
    panel.classList.add("open");
    container.classList.add("panel-open");
  } else {
    panel.classList.remove("open");
    container.classList.remove("panel-open");
  }
  localStorage.setItem("trainingPanelOpen", willOpen);
}

function updateTrainingPanel(training) {
  if (!training) return;

  const cleanText = (text) => {
    if (!text) return "-";
    // strip markdown: bold, italic, numbered lists, bullet points
    let clean = String(text)
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/^\d+\.\s+/gm, "")
      .replace(/^[-•]\s+/gm, "")
      .replace(/\n/g, " ")
      .trim();
    // cap at 120 chars
    if (clean.length > 120) clean = clean.slice(0, 117) + "...";
    return escapeHtml(clean);
  };

  document.getElementById("tWhatHappened").innerHTML = cleanText(
    training.what_happened,
  );
  document.getElementById("tNextMove").innerHTML = cleanText(
    training.next_move,
  );

  const ul = document.getElementById("tWatchFor");
  ul.innerHTML = "";
  (training.watch_for || []).slice(0, 2).forEach((tip) => {
    const li = document.createElement("li");
    li.innerHTML = cleanText(tip);
    ul.appendChild(li);
  });
}

// Training Q&A
function askTrainingCoach() {
  const input = document.getElementById("trainingQuestion");
  const answer = document.getElementById("trainingAnswer");
  const question = input.value.trim();
  if (!question) return;

  answer.textContent = "Thinking...";
  input.disabled = true;

  fetch("/api/training/ask", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": getSessionId(),
    },
    body: JSON.stringify({ question, style: trainingStyle }),
  })
    .then((r) => r.json())
    .then((data) => {
      const raw = data.answer || data.error || "No answer received.";
      answer.innerHTML = raw
        .split(/\n+/)
        .filter((l) => l.trim())
        .map((l) => `<p>${DOMPurify.sanitize(parseMarkdown(l))}</p>`)
        .join("");
      input.disabled = false;
      input.value = "";
      input.focus();
    })
    .catch((e) => {
      answer.textContent = "Error: " + e;
      input.disabled = false;
    });
}

// Quiz Panel
let currentQuizType = "stage";

function toggleQuizPanel() {
  const panel = document.getElementById("quizPanel");
  const container = document.querySelector(".container");
  const willOpen = !panel.classList.contains("open");
  closeAllPanels();
  if (willOpen) {
    panel.classList.add("open");
    container.classList.add("quiz-panel-open");
    fetchQuizQuestion();
  }
  localStorage.setItem("quizPanelOpen", willOpen);
}

function selectQuizType(type) {
  currentQuizType = type;
  // Update button states
  document.querySelectorAll(".quiz-type-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.id === `quiz-btn-${type}`);
  });
  // Clear previous feedback
  document.getElementById("quizFeedback").innerHTML = "";
  document.getElementById("quizAnswer").value = "";
  // Fetch new question
  fetchQuizQuestion();
}

function fetchQuizQuestion() {
  const questionEl = document.getElementById("quizQuestion");
  questionEl.textContent = "Loading question...";

  fetch(`/api/test/question?type=${currentQuizType}`, {
    headers: { "X-Session-ID": getSessionId() },
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        questionEl.textContent = data.question;
      } else {
        questionEl.textContent = data.error || "Failed to load question.";
      }
    })
    .catch((e) => {
      questionEl.textContent = "Error loading question: " + e;
    });
}

function submitQuiz() {
  const answer = document.getElementById("quizAnswer").value.trim();
  if (!answer) {
    alert("Please enter an answer.");
    return;
  }

  const submitBtn = document.getElementById("quizSubmitBtn");
  const feedbackEl = document.getElementById("quizFeedback");
  submitBtn.disabled = true;
  feedbackEl.innerHTML = '<div style="color:#8b8fa3">Evaluating...</div>';

  // Build request body based on quiz type
  let body = {};
  let endpoint = "";
  if (currentQuizType === "stage") {
    body = { answer };
    endpoint = "/api/test/stage";
  } else if (currentQuizType === "next_move") {
    body = { response: answer };
    endpoint = "/api/test/next-move";
  } else {
    body = { explanation: answer };
    endpoint = "/api/test/direction";
  }

  fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": getSessionId(),
    },
    body: JSON.stringify(body),
  })
    .then((r) => r.json())
    .then((data) => {
      submitBtn.disabled = false;
      if (data.success) {
        displayQuizFeedback(data);
      } else {
        feedbackEl.innerHTML = "";
        const err = document.createElement("div");
        err.className = "quiz-feedback incorrect";
        err.textContent = data.error || "Error";
        feedbackEl.appendChild(err);
      }
    })
    .catch((e) => {
      submitBtn.disabled = false;
      feedbackEl.innerHTML = "";
      const err = document.createElement("div");
      err.className = "quiz-feedback incorrect";
      err.textContent = "Error: " + e;
      feedbackEl.appendChild(err);
    });
}

function displayQuizFeedback(data) {
  const feedbackEl = document.getElementById("quizFeedback");

  // Determine score and class
  let score, feedbackClass, feedbackText;

  if (currentQuizType === "stage") {
    // Stage quiz: correct/incorrect
    score = data.correct ? "100%" : "0%";
    feedbackClass = data.correct ? "correct" : "incorrect";
    feedbackText = data.feedback;
  } else {
    // LLM-based quizzes: 0-100 score
    if (data.score === null || data.score === undefined) {
      score = "Unavailable";
      feedbackClass = "partial";
    } else {
      score = data.score + "%";
      if (data.score >= 70) feedbackClass = "correct";
      else if (data.score >= 40) feedbackClass = "partial";
      else feedbackClass = "incorrect";
    }
    feedbackText = data.feedback;
  }

  const safeFeedbackText = parseMarkdown(feedbackText || "");

  let html = `
          <div class="quiz-feedback ${feedbackClass}">
            <div class="quiz-score">${score}</div>
            <div class="quiz-feedback-text">${safeFeedbackText}</div>
        `;

  // Add details for LLM quizzes
  if (data.strengths && data.strengths.length) {
    html += '<div class="quiz-details"><strong>Strengths:</strong><ul>';
    data.strengths.forEach(
      (s) => (html += `<li>${parseMarkdown(String(s))}</li>`),
    );
    html += "</ul></div>";
  }
  if (data.improvements && data.improvements.length) {
    html += '<div class="quiz-details"><strong>Improvements:</strong><ul>';
    data.improvements.forEach(
      (s) => (html += `<li>${parseMarkdown(String(s))}</li>`),
    );
    html += "</ul></div>";
  }
  if (data.key_concepts_got && data.key_concepts_got.length) {
    html += '<div class="quiz-details"><strong>Concepts you got:</strong><ul>';
    data.key_concepts_got.forEach(
      (s) => (html += `<li>${parseMarkdown(String(s))}</li>`),
    );
    html += "</ul></div>";
  }
  if (data.key_concepts_missed && data.key_concepts_missed.length) {
    html +=
      '<div class="quiz-details"><strong>Concepts to review:</strong><ul>';
    data.key_concepts_missed.forEach(
      (s) => (html += `<li>${parseMarkdown(String(s))}</li>`),
    );
    html += "</ul></div>";
  }
  if (data.coach_tip) {
    html += `<div class="quiz-details"><strong>Coach tip:</strong> ${parseMarkdown(String(data.coach_tip))}</div>`;
  }

  // For stage quiz, show expected answer
  if (data.expected) {
    html += `<div class="quiz-details"><strong>Expected:</strong> ${escapeHtml(data.expected.stage)} / ${escapeHtml(data.expected.strategy)}</div>`;
  }

  html += "</div>";
  feedbackEl.innerHTML = html;
}

// Textarea Auto-resize
function autoResizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

// Keyboard Handler
// Enter = send, Shift+Enter = newline (default textarea behaviour)
function handleKeyDown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
  // Shift+Enter falls through - browser inserts newline naturally
}

// Reset Session
function resetChat() {
  if (!confirm("Reset conversation? This will clear all history.")) return;

  if (hasProspectContext()) {
    resetProspectSession();
    return;
  }

  fetch("/api/reset", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": getSessionId(),
    },
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.success) {
        document.getElementById("chatContainer").innerHTML = "";
        userTurnIndex = 0;
        clearStoredHistory();
        sessionId = null;
        clearStoredSessionId();
        updateStage("intent");
        updateStrategy("-");
        initChatbot();
      }
    })
    .catch((error) =>
      showToast("Reset didn't stick -- try one more time", "error"),
    );
}

async function resetProspectSession() {
  const oldSessionId = _prospectSessionId;
  try {
    const r = await fetch("/api/prospect/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        difficulty: _prospectDifficulty,
        product_type: _prospectProductType,
      }),
    });
    const data = await r.json();
    if (data.error) {
      showToast(data.error, "error");
      return;
    }
    hideTyping();
    // Clean up old session without blocking (fire-and-forget)
    if (oldSessionId) {
      fetch("/api/prospect/reset", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": oldSessionId,
        },
      }).catch(() => {});
    }
    applyProspectSessionFromServer(data.session_id, {
      state: data.state,
      persona: data.persona,
      difficulty: data.difficulty,
      product_type: _prospectProductType,
      message: data.message,
      latency_ms: data.latency_ms,
      provider: data.provider,
    });
  } catch (_) {
    showToast("Reset didn't stick -- try one more time", "error");
  }
}

function applyProspectSessionFromServer(sessionId, data) {
  _prospectMode = true;
  _prospectSessionId = sessionId;
  _prospectDifficulty = data.difficulty || "medium";
  if (data.product_type) _prospectProductType = data.product_type;
  _prospectMaxTurns = data.max_turns ?? null;
  _prospectScoringEnabled = data.scoring_enabled ?? true;
  _prospectFeedbackStyle = data.feedback_style || "coaching";
  syncKnowledgeBaseLink();
  syncModeChrome();
  clearProspectEvaluationPanel();

  closeAllPanels();

  // Show prospect panel
  document.getElementById("prospectPanel")?.classList.add("open");
  document.querySelector(".container")?.classList.add("prospect-panel-open");

  // Update header badges
  document.getElementById("strategyBadge").textContent = "PROSPECT MODE";
  document.getElementById("stageBadge").textContent =
    _prospectDifficulty.toUpperCase();

  // Hide sales mode buttons, show active prospect indicator
  document.getElementById("trainingToggleBtn").style.display = "none";
  document.getElementById("quizToggleBtn").style.display = "none";
  document.getElementById("prospectStartBtn").textContent = "Exit Prospect";
  document.getElementById("prospectStartBtn").onclick = endProspectMode;

  // Update panel info
  if (data.persona) {
    document.getElementById("prospectName").textContent =
      data.persona.name || "Alex";
    document.getElementById("prospectBackground").textContent =
      data.persona.background || "";
  }
  updateProspectDiffBadge(data.difficulty);
  updateProspectPanel(data.state);

  // Apply settings UI
  document
    .getElementById("prospectHintsToggle")
    .classList.toggle("on", _prospectSettings.showHints);
  document.getElementById("prospectCoachingSection").style.display =
    _prospectSettings.showHints ? "" : "none";
  document.getElementById("prospectEvalDisplay").value =
    _prospectSettings.evalDisplay;
  document.getElementById("prospectCoachingHint").textContent =
    _prospectScoringEnabled
      ? "Hints will appear after the next prospect reply."
      : "Scoring is disabled by config; session will run without evaluation.";

  // Clear chat and restore history
  document.getElementById("chatContainer").innerHTML = "";
  userTurnIndex = 0;

  const conversationHistory = normalizeProspectConversationHistory(data);
  if (conversationHistory.length > 0) {
    conversationHistory.forEach((msg, idx) => {
      const sender = msg.role === "assistant" ? "bot" : "user";
      let metrics = null;
      if (idx === conversationHistory.length - 1 && data.latency_ms) {
        metrics = {
          latency_ms: data.latency_ms || 0,
          provider: data.provider || "",
          input_length: 0,
          output_length: 0,
        };
      }
      addProspectMessage(msg.content, sender, metrics);
    });
  }
}

function saveProspectSettings() {
  _prospectSettings.evalDisplay = document.getElementById(
    "prospectEvalDisplay",
  ).value;
  localStorage.setItem("prospectSettings", JSON.stringify(_prospectSettings));
}

function toggleProspectHints() {
  const toggle = document.getElementById("prospectHintsToggle");
  _prospectSettings.showHints = !_prospectSettings.showHints;
  toggle.classList.toggle("on", _prospectSettings.showHints);
  document.getElementById("prospectCoachingSection").style.display =
    _prospectSettings.showHints ? "" : "none";
  localStorage.setItem("prospectSettings", JSON.stringify(_prospectSettings));
}

function toggleProspectSettings() {
  document.getElementById("prospectSettingsBody").classList.toggle("open");
}

function openProspectSetup() {
  // Product dropdown is already populated server-side; just sync UI chrome.
  syncModeChrome();
  document.getElementById("sendBtn").disabled = false;
  document.getElementById("prospectCoachingHint").textContent =
    "Hints will appear after the next prospect reply.";
}

function selectProspectDifficulty(diff, btn) {
  _prospectDifficulty = diff;
  document
    .querySelectorAll(".prospect-diff-btn")
    .forEach((b) => b.classList.remove("selected"));
  btn.classList.add("selected");
}

async function startProspectMode() {
  const startBtn = document.getElementById("prospectStartBtn");
  startBtn.disabled = true;
  startBtn.textContent = "Starting...";

  const product = document.getElementById("prospectProductSelect").value;
  _prospectProductType = product;

  try {
    const r = await fetch("/api/prospect/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        difficulty: _prospectDifficulty,
        product_type: product,
      }),
    });
    const data = await r.json();

    if (data.error) {
      showToast(data.error, "error");
      startBtn.disabled = false;
      startBtn.textContent = "Play Prospect";
      return;
    }

    clearProspectSessionState();
    history.replaceState(null, "", "/prospect");

    applyProspectSessionFromServer(data.session_id, {
      state: data.state,
      persona: data.persona,
      difficulty: data.difficulty,
      message: data.message,
      latency_ms: data.latency_ms,
      provider: data.provider,
    });
    // Re-enable the start/exit button now the UI has been applied
    startBtn.disabled = false;
    return; // button is now "Exit Prospect"
  } catch (e) {
    showToast("Failed to start prospect mode", "error");
  }
  startBtn.disabled = false;
  startBtn.textContent = "Play Prospect";
}

function endProspectMode() {
  try {
    if (_prospectMode && _prospectSessionId) {
      // Best-effort server reset; ignore network errors but continue UI cleanup
      fetch("/api/prospect/reset", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": _prospectSessionId,
        },
      }).catch(() => {});
    }
  } finally {
    // Always restore client UI state even if network call failed
    clearProspectSessionState();
    try {
      history.replaceState(null, "", "/");
    } catch (e) {}

    // Hide prospect panel safely
    const prospectPanel = document.getElementById("prospectPanel");
    if (prospectPanel) prospectPanel.classList.remove("open");
    const containerEl = document.querySelector(".container");
    if (containerEl) containerEl.classList.remove("prospect-panel-open");

    // Restore header buttons safely
    const trainingBtn = document.getElementById("trainingToggleBtn");
    const quizBtn = document.getElementById("quizToggleBtn");
    const startBtn = document.getElementById("prospectStartBtn");
    if (trainingBtn) trainingBtn.style.display = "";
    if (quizBtn) quizBtn.style.display = "";
    if (startBtn) {
      startBtn.textContent = "Play Prospect";
      startBtn.onclick = startProspectMode;
      startBtn.disabled = false;
    }

    // Clear chat and reinit normal mode
    const chatContainer = document.getElementById("chatContainer");
    if (chatContainer) chatContainer.innerHTML = "";
    userTurnIndex = 0;
    clearStoredHistory();
    sessionId = null;
    syncModeChrome();
    // Reinitialize the main chatbot; safe to call even if already active
    try {
      initChatbot();
    } catch (e) {
      console.warn("Failed to re-init chatbot after exiting prospect mode:", e);
    }
  }
}

function updateProspectDiffBadge(diff) {
  const el = document.getElementById("prospectDiffBadge");
  el.innerHTML = `<span class="prospect-difficulty-badge ${diff}">${diff}</span>`;
}

function updateProspectPanel(state) {
  if (!state) return;
  const readiness = Math.round((state.readiness || 0) * 100);
  const fill = document.getElementById("prospectReadinessFill");
  fill.style.width = Math.max(2, readiness) + "%";

  // Color: red → yellow → green
  if (readiness < 30) fill.style.background = "#ef4444";
  else if (readiness < 60) fill.style.background = "#eab308";
  else fill.style.background = "#22c55e";

  document.getElementById("prospectReadinessVal").textContent = readiness + "%";
  const turns = state.turn_count || 0;
  const max = _prospectMaxTurns;
  document.getElementById("prospectTurnCount").textContent = max
    ? `${turns} / ${max}`
    : turns;
}

function addProspectMessage(text, sender, metrics = null) {
  // Reuse the existing message rendering
  const container = document.getElementById("chatContainer");
  let msgIdx = null;
  if (sender === "user") {
    msgIdx = userTurnIndex * 2;
    userTurnIndex += 1;
  }
  const el = createMessageElement(text, sender, msgIdx, metrics);
  container.appendChild(el);
  requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });
}

function sendProspectMessage() {
  // Guard: ensure prospect session exists
  if (!_prospectSessionId) {
    showToast("No active prospect session. Start Prospect first.", "error");
    openProspectSetup();
    return;
  }

  const input = document.getElementById("messageInput");
  const message = input.value.trim();
  if (!message || isTyping) return;

  isTyping = true;
  document.getElementById("sendBtn").disabled = true;

  addProspectMessage(message, "user");
  input.value = "";
  autoResizeTextarea(input);
  showTyping();

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 25000);

  fetch("/api/prospect/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": _prospectSessionId,
    },
    body: JSON.stringify({
      message,
      show_hints: _prospectSettings.showHints,
    }),
    signal: controller.signal,
  })
    .then((r) => {
      clearTimeout(timeoutId);
      return r.json();
    })
    .then((data) => {
      hideTyping();
      if (data.error) {
        if (handleProspectSessionError(data)) return;
        showToast(data.error, "error");
        return;
      }
      const metrics = {
        latency_ms: data.latency_ms || 0,
        provider: data.provider || "",
        input_length: 0,
        output_length: 0,
      };
      addProspectMessage(data.message, "bot", metrics);
      updateProspectPanel(data.state);

      // Show coaching hint if enabled
      if (data.coaching && _prospectSettings.showHints) {
        document.getElementById("prospectCoachingHint").textContent =
          data.coaching.hint;
        document.getElementById("prospectCoachingSection").style.display = "";
      } else if (_prospectSettings.showHints) {
        document.getElementById("prospectCoachingHint").textContent =
          "Hints will appear after the next prospect reply.";
      }

      // Check if session ended
      if (data.ended) {
        handleProspectEnd(data.outcome);
      }
    })
    .catch((e) => {
      clearTimeout(timeoutId);
      hideTyping();
      const msg =
        e.name === "AbortError"
          ? "Request timed out -- send that again"
          : "Network hiccup -- try that once more";
      showToast(msg, "error");
    });
}

function handleProspectEnd(outcome) {
  // Disable input
  document.getElementById("sendBtn").disabled = true;

  // Auto-request evaluation
  requestProspectEvaluation();
}

async function endAndScore() {
  if (!_prospectSessionId) return;
  document.getElementById("sendBtn").disabled = true;
  await requestProspectEvaluation();
}

async function requestProspectEvaluation() {
  const container = document.getElementById("chatContainer");

  // Show loading message
  const loadingMsg = document.createElement("div");
  loadingMsg.className = "message bot";
  loadingMsg.innerHTML =
    '<div class="message-bubble" style="color:#06b6d4">Generating evaluation...</div>';
  container.appendChild(loadingMsg);
  container.scrollTop = container.scrollHeight;

  try {
    const r = await fetch("/api/prospect/evaluate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": _prospectSessionId,
      },
    });
    const data = await r.json();
    loadingMsg.remove();

    if (!data.success) {
      if (handleProspectSessionError(data)) return;
      addProspectMessage(
        "Evaluation failed: " + (data.error || "Unknown error"),
        "bot",
      );
      return;
    }

    renderEvaluation(data, _prospectSettings.evalDisplay);
  } catch (e) {
    loadingMsg.remove();
    addProspectMessage("Evaluation error: " + e, "bot");
  }
}

function renderEvaluation(data, displayMode) {
  const html = buildEvaluationHTML(data);

  if (displayMode === "modal") {
    renderEvalModal(html);
  } else if (displayMode === "panel") {
    renderEvalPanel(html);
  } else {
    // Inline (default)
    renderEvalInline(html);
  }
}

function buildEvaluationHTML(data) {
  const gradeClass = "grade-" + (data.grade || "c").toLowerCase();
  const outcomeClass = data.outcome || "incomplete";
  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");

  let criteriaHtml = "";
  if (data.criteria_scores) {
    for (const [name, info] of Object.entries(data.criteria_scores)) {
      const safeFeedback = escapeHtml(info.feedback || "");
      criteriaHtml += `
              <div class="prospect-eval-criterion">
                <div>
                  <div class="prospect-eval-criterion-name">${escapeHtml(name.replace(/_/g, " "))}</div>
                  <div class="prospect-eval-criterion-feedback">${safeFeedback}</div>
                </div>
                <div class="prospect-eval-criterion-score">${info.score}%</div>
              </div>`;
    }
  }

  let strengthsHtml = "";
  if (data.strengths && data.strengths.length) {
    strengthsHtml = `<div class="prospect-eval-list">
            <div class="prospect-eval-list-title">Strengths</div>
            <ul>${data.strengths.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
          </div>`;
  }

  let improvementsHtml = "";
  if (data.improvements && data.improvements.length) {
    improvementsHtml = `<div class="prospect-eval-list">
            <div class="prospect-eval-list-title">Areas for Improvement</div>
            <ul>${data.improvements.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>
          </div>`;
  }

  const coachTipHtml = data.coach_tip
    ? `<div class="prospect-coaching"><strong>Coach tip:</strong> ${escapeHtml(data.coach_tip)}</div>`
    : "";

  return `
          <div class="prospect-eval-header">
            <div class="prospect-eval-score">${data.overall_score || 0}%</div>
            <div class="prospect-eval-grade ${gradeClass}">${escapeHtml(data.grade || "?")}</div>
          </div>
          <div class="prospect-eval-outcome ${outcomeClass}">
            ${data.outcome === "sold" ? "Sale Made" : data.outcome === "walked" ? "Prospect Walked Away" : "Incomplete"}
          </div>
          <div class="prospect-eval-criteria">${criteriaHtml}</div>
          ${strengthsHtml}
          ${improvementsHtml}
          ${coachTipHtml}
          ${data.summary ? `<div class="prospect-eval-summary">${escapeHtml(data.summary)}</div>` : ""}
          <button class="prospect-try-again-btn" onclick="tryAgainProspect()">Try again</button>
        `;
}

function renderEvalInline(html) {
  const container = document.getElementById("chatContainer");
  const card = document.createElement("div");
  card.className = "prospect-evaluation";
  card.innerHTML = html;
  container.appendChild(card);
  container.scrollTop = container.scrollHeight;
}

function renderEvalModal(html) {
  const overlay = document.createElement("div");
  overlay.id = "prospectEvalModal";
  overlay.style.cssText =
    "position:fixed;inset:0;background:rgba(0,0,0,0.7);z-index:300;display:flex;justify-content:center;align-items:center;overflow-y:auto;padding:20px";
  const card = document.createElement("div");
  card.className = "prospect-evaluation";
  card.style.cssText =
    "max-width:500px;width:100%;max-height:90vh;overflow-y:auto";
  card.innerHTML = html;
  overlay.appendChild(card);
  overlay.onclick = (e) => {
    if (e.target === overlay) overlay.remove();
  };
  document.body.appendChild(overlay);
}

function renderEvalPanel(html) {
  const body = document.querySelector("#prospectPanel .prospect-body");
  if (!body) return;

  let panel = document.getElementById("prospectEvalPanelContent");
  if (!panel) {
    panel = document.createElement("div");
    panel.id = "prospectEvalPanelContent";
    panel.style.cssText = "padding:16px";
    body.appendChild(panel);
  }

  panel.innerHTML = html;
}

function tryAgainProspect() {
  // Remove modal if exists
  const modal = document.getElementById("prospectEvalModal");
  if (modal) modal.remove();

  // End current session
  if (_prospectSessionId) {
    fetch("/api/prospect/reset", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": _prospectSessionId,
      },
    }).catch(() => {});
  }
  clearProspectSessionState();
  syncModeChrome();

  // Restore prospect panel body
  clearProspectEvaluationPanel();
  document.getElementById("prospectPanel").classList.remove("open");
  document.querySelector(".container").classList.remove("prospect-panel-open");

  // Re-enable send
  document.getElementById("sendBtn").disabled = false;

  // Restore start button
  const startBtn = document.getElementById("prospectStartBtn");
  startBtn.textContent = "Play Prospect";
  startBtn.onclick = startProspectMode;

  // Open setup again
  openProspectSetup();
}

// â”€â”€â”€ Speech module â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
let speechRecognizer;

function toggleMic() {
  const micBtn = document.getElementById("micBtn");
  const input = document.getElementById("messageInput");

  if (!speechRecognizer) {
    showToast("Speech not supported in this browser", "error");
    return;
  }

  if (speechRecognizer.isTranscribing) {
    showToast("Transcribing, please wait", "info");
    return;
  }

  if (speechRecognizer.isRecording) {
    speechRecognizer.stop();
    return;
  }

  micBtn.classList.add("recording");
  micBtn.innerHTML = "â¹";

  speechRecognizer.start(
    (text) => {
      if (currentTtsAudio) return; // echo guard: ignore while bot is speaking
      const parsed = parsePunctuation(text);
      input.value = (input.value || "") + parsed;
      autoResizeTextarea(input);
      _setDictationPreview("");

      scheduleVoiceAutoSend(input);
    },
    (text) => {
      if (currentTtsAudio) return;
      _setDictationPreview(text);
    },
    (state) => {
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "🎤";
      if (state?.canceled) {
        _setDictationPreview("");
        input.focus();
        return;
      }
      _setDictationPreview("");
      // On stop: let the pause-timer fire naturally; only flush if user typed.
      input.focus();
    },
    (err) => {
      console.warn("Mic Error:", err);
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "🎤";
      _setDictationPreview("");
      showToast(String(err || "Microphone error"), "error");
    },
  );
}

function resumeVoiceInputAfterTts() {
  window.__speechPausedForTTS = false;
  if (handsFreeMode) {
    startHandsFreeRecognition();
    return;
  }

  const input = document.getElementById("messageInput");
  if (input) input.focus();
}

function stopTtsPlayback({ resumeVoiceInput = false } = {}) {
  ttsPlaybackGeneration += 1;
  ttsPlaybackPending = false;

  if (ttsResumeWatchdogTimer) {
    clearTimeout(ttsResumeWatchdogTimer);
    ttsResumeWatchdogTimer = null;
  }

  if (currentTtsAudio) {
    currentTtsAudio.onended = null;
    currentTtsAudio.onerror = null;
    try {
      currentTtsAudio.pause();
    } catch (e) {}

    if (currentTtsAudio._blobUrl) {
      URL.revokeObjectURL(currentTtsAudio._blobUrl);
    }
    currentTtsAudio = null;
  }

  document.querySelectorAll(".tts-btn.speaking").forEach((btn) => {
    btn.classList.remove("speaking");
  });

  const interruptBtn = document.getElementById("interruptBtn");
  if (interruptBtn) interruptBtn.style.display = "none";
  _showTTSBanner(false);

  if (resumeVoiceInput) {
    resumeVoiceInputAfterTts();
  }
}

function _nativeSpeechRate() {
  const rate = 1 + ttsPlaybackSpeed / 100;
  return Math.min(10, Math.max(0.1, rate));
}

function _hasPuterTts() {
  return Boolean(window.puter?.ai?.txt2speech);
}

async function createPuterTtsHandle(text) {
  if (!_hasPuterTts()) {
    return null;
  }

  try {
    const audio = await window.puter.ai.txt2speech(text, {
      language: "en-US",
      engine: "neural",
    });

    if (!audio || typeof audio.play !== "function") {
      return null;
    }

    let onended = null;
    let onerror = null;
    const finish = () => {
      if (onended) onended();
    };
    const fail = () => {
      if (onerror) onerror();
    };

    if (typeof audio.addEventListener === "function") {
      audio.addEventListener("ended", finish, { once: true });
      audio.addEventListener("error", fail, { once: true });
    } else {
      audio.onended = finish;
      audio.onerror = fail;
    }

    return {
      kind: "puter",
      pause() {
        try {
          audio.pause();
        } catch (e) {}
      },
      play() {
        return Promise.resolve(audio.play());
      },
      set onended(fn) {
        onended = fn;
      },
      set onerror(fn) {
        onerror = fn;
      },
    };
  } catch (error) {
    console.warn("Puter TTS failed:", error);
    return null;
  }
}

function createNativeTtsHandle(text) {
  if (!("speechSynthesis" in window) || !window.SpeechSynthesisUtterance) {
    return null;
  }

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = _nativeSpeechRate();

  let onended = null;
  let onerror = null;

  utterance.onend = () => {
    if (onended) onended();
  };
  utterance.onerror = () => {
    if (onerror) onerror();
  };

  return {
    kind: "native",
    pause() {
      speechSynthesis.cancel();
    },
    play() {
      try {
        speechSynthesis.cancel();
        speechSynthesis.speak(utterance);
        return Promise.resolve();
      } catch (err) {
        return Promise.reject(err);
      }
    },
    set onended(fn) {
      onended = fn;
    },
    set onerror(fn) {
      onerror = fn;
    },
  };
}

async function createAssistantTtsHandle(text) {
  if (ttsPlaybackSpeed === 0) {
    const puterHandle = await createPuterTtsHandle(text);
    if (puterHandle) {
      return puterHandle;
    }
  }

  const nativeHandle = createNativeTtsHandle(text);
  if (nativeHandle) {
    return nativeHandle;
  }

  if (ttsPlaybackSpeed !== 0) {
    const puterHandle = await createPuterTtsHandle(text);
    if (puterHandle) {
      return puterHandle;
    }
  }

  return null;
}

async function playAssistantTts(text, { onStart } = {}) {
  if (!text) return;
  stopTtsPlayback();
  const playbackGeneration = ttsPlaybackGeneration;
  ttsPlaybackPending = true;

  try {
    if (speechRecognizer && speechRecognizer.isRecording) {
      stopHandsFreeRecognition();
      window.__speechPausedForTTS = true;
    }
  } catch (e) {}

  const handle = await createAssistantTtsHandle(text);
  if (playbackGeneration !== ttsPlaybackGeneration) {
    ttsPlaybackPending = false;
    try {
      handle?.pause?.();
    } catch (e) {}
    return;
  }

  ttsPlaybackPending = false;
  currentTtsAudio = handle;
  if (!currentTtsAudio) {
    console.warn("Failed to generate TTS audio.");
    showToast("Voice playback is unavailable", "error");
    resumeVoiceInputAfterTts();
    return;
  }

  if (onStart) {
    try {
      onStart(currentTtsAudio);
    } catch (e) {}
  }

  const interruptBtn = document.getElementById("interruptBtn");
  if (interruptBtn) interruptBtn.style.display = "inline-block";
  _showTTSBanner(true);

  const finishPlayback = () => {
    stopTtsPlayback();
    resumeVoiceInputAfterTts();
  };

  // Watchdog: if onended never fires (browser tab hidden, audio error), force-resume.
  if (ttsResumeWatchdogTimer) clearTimeout(ttsResumeWatchdogTimer);
  ttsResumeWatchdogTimer = setTimeout(() => {
    ttsResumeWatchdogTimer = null;
    if (currentTtsAudio) {
      console.warn("TTS watchdog: forcing resume");
      finishPlayback();
    }
  }, TTS_RESUME_WATCHDOG_MS);

  currentTtsAudio.onended = finishPlayback;
  currentTtsAudio.onerror = finishPlayback;

  try {
    await currentTtsAudio.play();
  } catch (error) {
    console.warn("TTS playback failed:", error);
    showToast("Could not play the assistant voice", "error");
    finishPlayback();
  }
}

// Centralised helpers for hands-free STT control
function startHandsFreeRecognition() {
  if (!speechRecognizer?.recognition) {
    showToast(
      "Hands-free mode needs native speech recognition. Use the mic button instead.",
      "info",
    );
    return false;
  }
  if (speechRecognizer.isRecording) return true;

  const inputEl = document.getElementById("messageInput");
  if (!inputEl) return false;
  const micBtn = document.getElementById("micBtn");
  if (micBtn) {
    micBtn.classList.add("recording");
    micBtn.innerHTML = "â¹";
  }

  try {
    speechRecognizer.start(
      (text) => {
        try {
          if (currentTtsAudio) return; // echo guard: bot is speaking
          const voiceCommand = parseFlowVoiceCommand(text);
          if (voiceCommand) {
            clearVoiceSilenceTimer();
            executeFlowVoiceCommand(voiceCommand);
            autoResizeTextarea(inputEl);
            _setDictationPreview("");
            return;
          }

          const parsed = parsePunctuation(text);
          inputEl.value = (inputEl.value || "") + parsed;
          autoResizeTextarea(inputEl);
          _setDictationPreview("");

          scheduleVoiceAutoSend(inputEl);
        } catch (e) {
          console.warn("dictation final handler error:", e);
        }
      },
      (interim) => {
        try {
          if (currentTtsAudio) return;
          _setDictationPreview(interim);
        } catch (e) {
          console.warn("dictation interim handler error:", e);
        }
      },
      () => {
        // update mic UI
        const mic = document.getElementById("micBtn");
        if (mic) {
          mic.classList.remove("recording");
          mic.innerHTML = "🎤";
        }
        // gentle restart if still in hands-free mode
        if (
          handsFreeMode &&
          speechRecognizer &&
          !speechRecognizer.isRecording
        ) {
          const attempt = _handsFreeRestartAttempts;
          const delay = Math.min(200 * Math.pow(2, attempt), 5000);
          setTimeout(() => {
            try {
              if (!handsFreeMode) return;
              if (!speechRecognizer.isRecording) {
                const started = startHandsFreeRecognition();
                if (started) {
                  _handsFreeRestartAttempts = 0;
                } else {
                  _handsFreeRestartAttempts = Math.min(attempt + 1, 5);
                }
              }
            } catch (e) {
              console.warn("hands-free restart error:", e);
            }
          }, delay);
        }
      },
      (err) => {
        console.warn("Speech error:", err);
      },
    );
    return true;
  } catch (e) {
    console.warn("startHandsFreeRecognition error:", e);
    if (micBtn) {
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "🎤";
    }
    return false;
  }
}

function stopHandsFreeRecognition() {
  try {
    if (speechRecognizer && speechRecognizer.isRecording)
      speechRecognizer.stop();
  } catch (e) {
    console.warn("stopHandsFreeRecognition error:", e);
  }
  const mic = document.getElementById("micBtn");
  if (mic) {
    mic.classList.remove("recording");
    mic.innerHTML = "🎤";
  }
  _setDictationPreview("");
}

function interruptAssistant() {
  // Stop any TTS and resume listening if appropriate
  try {
    stopTtsPlayback({ resumeVoiceInput: true });
  } catch (e) {
    console.warn("interruptAssistant error:", e);
  }
}

function toggleVoiceMode() {
  handsFreeMode = !handsFreeMode;
  const btn = document.getElementById("voiceModeBtn");
  const indicator = document.getElementById("voiceModeIndicator");
  const inputArea = document.querySelector(".input-area");
  if (btn) btn.classList.toggle("active", handsFreeMode);
  if (indicator) indicator.textContent = handsFreeMode ? "🔊" : "⌨️";
  if (inputArea) inputArea.classList.toggle("hands-free-active", handsFreeMode);
  stopTtsPlayback();
  if (!handsFreeMode) {
    clearVoiceSilenceTimer();
    _handsFreeRestartAttempts = 0;
  }

  showToast(
    handsFreeMode
      ? "Conversational Mode ON - speak, auto-send, auto-play response"
      : "Conversational Mode OFF - dictation only",
      "info",
  );

  // Start/stop continuous recording when toggling hands-free
  try {
    if (handsFreeMode) {
      if (!speechRecognizer || !speechRecognizer.recognition) {
        showToast("Speech not supported in this browser", "error");
        // revert UI toggles
        handsFreeMode = false;
        if (btn) btn.classList.toggle("active", false);
        if (indicator) indicator.textContent = "⌨️";
        if (inputArea) inputArea.classList.toggle("hands-free-active", false);
        return;
      }

      // Start centralized hands-free recognition
      startHandsFreeRecognition();
    } else {
      // Turn hands-free OFF → stop recording via helper
      stopHandsFreeRecognition();
    }
  } catch (e) {
    console.warn("toggleVoiceMode error:", e);
  }
}

// ============================================
// TRAINING SCORE UI
// ============================================

async function scoreSession() {
  const container = document.getElementById("chatContainer");

  // Show loading message
  const loadingMsg = document.createElement("div");
  loadingMsg.className = "message bot";
  loadingMsg.innerHTML =
    '<div class="message-bubble" style="color:#10b981">Calculating your session score...</div>';
  container.appendChild(loadingMsg);
  container.scrollTop = container.scrollHeight;

  try {
    const headers = { "Content-Type": "application/json" };
    const sid = getSessionId();
    if (sid) {
      headers["X-Session-ID"] = sid;
    }

    const response = await fetch("/api/score", {
      method: "GET",
      headers: headers,
    });

    const data = await response.json();
    loadingMsg.remove();

    if (data.success && data.score) {
      renderSessionScore(data.score);
    } else {
      loadingMsg.innerHTML = `<div class="message-bubble error">Error: ${data.error || "Failed to generate score"}</div>`;
      container.appendChild(loadingMsg);
    }
  } catch (err) {
    loadingMsg.innerHTML = `<div class="message-bubble error">Error connection: ${err}</div>`;
    container.appendChild(loadingMsg);
  }
}

function renderSessionScore(scoreData) {
  const container = document.getElementById("chatContainer");
  const scoreCard = document.createElement("div");
  scoreCard.className = "message bot";

  const b = scoreData.breakdown;
  const m = scoreData.metrics;

  scoreCard.innerHTML = `<div class="score-card">
      <div class="score-card-title">Session Training Score: ${scoreData.total_score}/100</div>
      <div class="score-card-subtitle">Breakdown of your interaction:</div>
      <div class="score-breakdown">
        <div class="score-row"><span>Stage Progression (30):</span><span>${b.stage_progression}</span></div>
        <div class="score-row"><span>Signal Detection (25):</span><span>${b.signal_detection}</span></div>
        <div class="score-row"><span>Objection Handling (20):</span><span>${b.objection_handling}</span></div>
        <div class="score-row"><span>Questioning Depth (15):</span><span>${b.questioning_depth}</span></div>
        <div class="score-row"><span>Conv. Length (10):</span><span>${b.conversation_length}</span></div>
      </div>
      <div class="score-details">
        <strong>Details:</strong>
        Stages Reached: ${m.stages_reached.join(", ") || "None"}<br>
        Signal Ratio: ${m.signal_ratio}<br>
        Total Turns: ${m.turns}
      </div>
    </div>`;
  container.appendChild(scoreCard);
  container.scrollTop = container.scrollHeight;
}

// â”€â”€â”€ Feedback Widget â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€ï¿½ï¿½â”€â”€â”€â”€â”€
let _fbRating = 0;

function toggleFeedback() {
  const dd = document.getElementById("feedbackDropdown");
  dd.classList.toggle("open");
}

function setFbRating(val) {
  _fbRating = val;
  document.querySelectorAll(".fb-star").forEach((s) => {
    s.classList.toggle("active", parseInt(s.dataset.val) <= val);
  });
}

async function submitFeedback() {
  const comment = document.getElementById("fbComment").value.trim();
  if (!_fbRating && !comment) return;

  const btn = document.getElementById("fbSubmitBtn");
  btn.disabled = true;

  try {
    const r = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rating: _fbRating || null,
        comment: comment || null,
        page: _prospectMode ? "prospect" : "chat",
      }),
    });
    const d = await r.json();
    if (d.success) {
      const dd = document.getElementById("feedbackDropdown");
      dd.innerHTML = '<div class="fb-thanks">Thanks for your feedback!</div>';
      setTimeout(() => {
        dd.classList.remove("open");
        dd.innerHTML = buildFeedbackForm();
        _fbRating = 0;
      }, 1500);
    }
  } catch (e) {
    showToast("Failed to send feedback", "error");
  } finally {
    btn.disabled = false;
  }
}

function buildFeedbackForm() {
  return `
    <div class="fb-title">Quick Feedback</div>
    <div class="fb-stars" id="fbStars">
      <button class="fb-star" data-val="1" onclick="setFbRating(1)">&#9733;</button>
      <button class="fb-star" data-val="2" onclick="setFbRating(2)">&#9733;</button>
      <button class="fb-star" data-val="3" onclick="setFbRating(3)">&#9733;</button>
      <button class="fb-star" data-val="4" onclick="setFbRating(4)">&#9733;</button>
      <button class="fb-star" data-val="5" onclick="setFbRating(5)">&#9733;</button>
    </div>
    <label class="sr-only" for="fbComment">Feedback comment</label>
    <textarea id="fbComment" class="fb-comment" placeholder="Any thoughts? (optional)" maxlength="500"></textarea>
    <button class="fb-submit" id="fbSubmitBtn" onclick="submitFeedback()">Send Feedback</button>`;
}

// â”€â”€â”€ Page Load Initialization â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    initTtsSpeedControl();
  });
} else {
  // DOM is already loaded
  initTtsSpeedControl();
}
