
// Keep only the in-memory conversation copy used by the UI.
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

function clearStaleOverlayState() {
  closeResetModal();
  closeResetMenu();
  document.getElementById("feedbackDropdown")?.classList.remove("open");
  document.getElementById("prospectEvalModal")?.remove();
  document.getElementById("quizPanel")?.classList.remove("open");
  if (!isDedicatedProspectPage()) {
    document.getElementById("prospectPanel")?.classList.remove("open");
  }
  document
    .querySelector(".container")
    ?.classList.remove("quiz-panel-open", "prospect-panel-open");
  localStorage.setItem("quizPanelOpen", "false");
  document.body.classList.remove("panel-open");
  document.body.style.overflow = "";
}

function normalizeKey(value) {
  return String(value || "")
    .trim()
    .toLowerCase();
}

function appendChatMessage(
  text,
  sender,
  metrics = null,
  { updateCache = true, msgIdx = null } = {},
) {
  const container = document.getElementById("chatContainer");
  setIntroVisibility(true);
  if (sender === "user" && msgIdx === null) {
    msgIdx = updateCache ? _cachedHistory.length : userTurnIndex * 2;
    userTurnIndex += 1;
  }

  const el = createMessageElement(text, sender, msgIdx, metrics);
  container.appendChild(el);
  requestAnimationFrame(() => {
    container.scrollTop = container.scrollHeight;
  });

  if (!updateCache) return;

  _cachedHistory.push({
    role: sender === "user" ? "user" : "assistant",
    content: text,
  });
  trimHistoryCache();
}

function getStrategyMeta(strategy) {
  const key = normalizeKey(strategy);
  return (
    STRATEGY_META[key] || {
      label: key ? key.replace(/\b\w/g, (m) => m.toUpperCase()) : "Not started",
      note: STRATEGY_META["-"].note,
    }
  );
}

function getStageMeta(stage) {
  const key = normalizeKey(stage);
  return FLOW_STAGE_META[key] || FLOW_STAGE_META.default;
}

function getCurrentFlowOrder() {
  const key = normalizeKey(_currentStrategy);
  return FLOW_STAGE_ORDER[key] || FLOW_STAGE_ORDER.consultative;
}

function updateWorkflowProgress() {
  const progressEl = document.getElementById("workflowProgress");
  if (!progressEl) return;

  if (_prospectMode || normalizeKey(_currentStrategy) === "prospect mode") {
    progressEl.innerHTML = `
      <div class="progress-step current">
        <span class="progress-dot" aria-hidden="true"></span>
        <span class="progress-label">Prospect practice live</span>
      </div>
    `;
    return;
  }

  const stages = getCurrentFlowOrder();
  const currentStageKey = normalizeKey(_currentStage);
  const currentIdx = stages.indexOf(currentStageKey);

  progressEl.innerHTML = "";
  stages.forEach((stage, idx) => {
    const meta = getStageMeta(stage);
    const step = document.createElement("div");
    const isCurrent = stage === currentStageKey;
    const isCompleted = currentIdx >= 0 && idx < currentIdx;
    step.className = `progress-step${isCurrent ? " current" : ""}${isCompleted ? " completed" : ""}`;
    step.innerHTML = `
      <span class="progress-dot" aria-hidden="true"></span>
      <span class="progress-label">${meta.label}</span>
    `;
    progressEl.appendChild(step);
  });
}

function updateStatusNote(note) {
  const noteEl = document.getElementById("stageStatusNote");
  if (noteEl) noteEl.textContent = note;
}

function setIntroVisibility(hidden) {
  const intro = document.getElementById("chatIntroCard");
  if (!intro) return;
  intro.classList.toggle("hidden", hidden);
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

function replaceConversationHistory(history) {
  _cachedHistory = normalizeConversationHistory(history);
  trimHistoryCache();
  const container = document.getElementById("chatContainer");
  container.innerHTML = "";
  userTurnIndex = 0;
  setIntroVisibility(Array.isArray(history) && history.length > 0);
  if (Array.isArray(history)) {
    history.forEach((m, idx) =>
      renderMessage(m.content, m.role === "user" ? "user" : "bot", idx),
    );
  }
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
        const textSpan = document.createElement("span");
        if (sender === "bot") {
          textSpan.innerHTML = DOMPurify.sanitize(parseMarkdown(l));
        } else {
          textSpan.textContent = l;
        }
        return textSpan.outerHTML;
      })
      .join("<br>");
  }

  const actions = document.createElement("div");
  actions.className = "message-actions";

  if (sender === "bot") {
    const btn = Object.assign(document.createElement("button"), {
      className: "tts-btn",
      innerHTML: "Listen",
      title: "Listen to this response",
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
      innerHTML: "Edit",
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
    const latencyMs = Number(metrics.latency_ms || 0);
    let metricsText = `${latencyMs.toFixed(1)}ms`;
    if (metrics.provider) metricsText += ` - ${metrics.provider}`;
    if (metrics.input_length || metrics.output_length)
      metricsText += ` - ${metrics.input_length}->${metrics.output_length}`;
    metricsDiv.textContent = metricsText;
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
        _sessionRecoveryInProgress = false;
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
      _sessionRecoveryInProgress = false;
    })
    .catch((error) => {
      _sessionRecoveryInProgress = false;
      showToast("Connection error - please refresh", "error");
    });
}

// renderMessage Function
// Render-only (no cache side effects). Used during history restore.
function renderMessage(text, sender, msgIdx = null) {
  appendChatMessage(text, sender, null, { updateCache: false, msgIdx });
}

// addMessage Function
function addMessage(text, sender, metrics = null) {
  appendChatMessage(text, sender, metrics);
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
    replaceConversationHistory(_cachedHistory);
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

// Stage and strategy badge helpers
function updateStage(stage) {
  _currentStage = normalizeKey(stage || "intent");
  const meta = getStageMeta(_currentStage);
  const badge = document.getElementById("stageBadge");
  if (badge) badge.textContent = meta.label;
  updateStatusNote(meta.note);
  updateWorkflowProgress();
}

function syncStrategySelectors(strategy) {
  const normalized = String(strategy || "")
    .trim()
    .toLowerCase();
  const known = new Set(["consultative", "transactional"]);
  ["strategySelectMain"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.value = known.has(normalized) ? normalized : "";
  });
}

function updateStrategy(strategy) {
  _currentStrategy = normalizeKey(strategy || "-");
  const meta = getStrategyMeta(_currentStrategy);
  const badge = document.getElementById("strategyBadge");
  if (badge) badge.textContent = meta.label;
  syncStrategySelectors(strategy);
  if (_currentStrategy === "-" || _currentStrategy === "prospect mode") {
    updateStatusNote(meta.note);
  }
  updateWorkflowProgress();
}

// Update the stage and strategy UI in one place
function updateSessionUI(data) {
  const stageSelectSource = document.getElementById("stageSelectMain");

  if (data.stage) updateStage(data.stage);
  if (data.strategy) {
    const strategyChanged = normalizeKey(data.strategy) !== _currentStrategy;
    updateStrategy(data.strategy);
    if (document.getElementById("stageSelectMain")) {
      if (strategyChanged || _loadedStagesForStrategy === null) {
        _loadedStagesForStrategy = normalizeKey(data.strategy);
        loadStageOptions();
      } else {
        // Strategy unchanged - just sync the selected value without an API call
        populateStageSelects(
          [...(stageSelectSource?.options ?? [])]
            .map((o) => o.value)
            .filter(Boolean),
          data.stage || _currentStage,
        );
      }
    }
  } else if (data.stage) {
    // Stage changed but strategy didn't come back - sync select value only
    populateStageSelects(
      [...(stageSelectSource?.options ?? [])]
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

function confirmResetChat() {
  closeResetModal();
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
        setIntroVisibility(false);
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

function toggleResetMenu() {
  const menu = document.getElementById("resetMenu");
  const btn = document.querySelector(".overflow-btn");
  const willOpen = !menu?.classList.contains("open");
  menu?.classList.toggle("open", willOpen);
  btn?.setAttribute("aria-expanded", willOpen ? "true" : "false");
}

function closeResetMenu() {
  const menu = document.getElementById("resetMenu");
  const btn = document.querySelector(".overflow-btn");
  menu?.classList.remove("open");
  btn?.setAttribute("aria-expanded", "false");
}

function openResetModal() {
  closeResetMenu();
  document.getElementById("resetModal")?.classList.add("open");
  document.getElementById("resetModal")?.setAttribute("aria-hidden", "false");
}

function closeResetModal() {
  document.getElementById("resetModal")?.classList.remove("open");
  document.getElementById("resetModal")?.setAttribute("aria-hidden", "true");
}

function handleResetBackdrop(event) {
  if (event.target?.id === "resetModal") {
    closeResetModal();
  }
}

