// NOTE: Prospect product dropdowns are populated server-side by Flask/Jinja in
// index.html from backend.app._prospect_product_groups(). No JS fetch is needed.

function syncProspectProductSelects(productType) {
  const transactionalSelect = document.getElementById(
    "prospectTransactionalSelect",
  );
  const consultativeSelect = document.getElementById(
    "prospectConsultativeSelect",
  );

  if (transactionalSelect) {
    transactionalSelect.value =
      transactionalSelect.querySelector(`option[value="${productType}"]`)
        ? productType
        : "default";
  }
  if (consultativeSelect) {
    consultativeSelect.value =
      consultativeSelect.querySelector(`option[value="${productType}"]`)
        ? productType
        : "default";
  }
}

function selectProspectProduct(category, selectEl) {
  const otherSelectId =
    category === "transactional"
      ? "prospectConsultativeSelect"
      : "prospectTransactionalSelect";
  const otherSelect = document.getElementById(otherSelectId);

  if (selectEl.value !== "default" && otherSelect && otherSelect.value !== "default") {
    otherSelect.value = "default";
  }
  _prospectProductType = selectEl.value;
}

function syncKnowledgeBaseLink() {
  const link = document.getElementById("knowledgeBaseLink");
  if (!link) return;

  const isProspectContext = isDedicatedProspectPage() || _prospectMode;

  link.href = isProspectContext ? "/knowledge?mode=prospect" : "/knowledge";
  const title = link.querySelector(".tool-title");
  const copy = link.querySelector(".tool-copy");
  if (title) {
    title.textContent = isProspectContext ? "Prospect knowledge" : "Knowledge";
  }
  if (copy) {
    copy.textContent = isProspectContext
      ? "Review notes tied to your prospect roleplay."
      : "Browse notes and product details.";
  }
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
  setTrainingPanelEmptyState();
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

async function resetProspectSession() {
  const oldSessionId = _prospectSessionId;
  try {
    const response = await fetch("/api/prospect/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        difficulty: _prospectDifficulty,
        product_type: _prospectProductType,
      }),
    });
    const data = await response.json();
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
  syncPanelShellState();

  // Update header badges
  updateStrategy("prospect mode");
  updateStage("default");
  updateStatusNote(
    "Practice this buyer persona and watch readiness change as you respond.",
  );

  // Hide sales mode buttons, show active prospect indicator
  document.getElementById("trainingToggleBtn").style.display = "none";
  document.getElementById("quizToggleBtn").style.display = "none";
  document.getElementById("prospectStartBtn").textContent =
    "Exit prospect practice";
  document.getElementById("prospectStartBtn").onclick = endProspectMode;

  // Update panel info
  if (data.persona) {
    document.getElementById("prospectName").textContent =
      data.persona.name || "Alex";
    document.getElementById("prospectBackground").textContent =
      data.persona.background || "";
  }
  syncProspectProductSelects(_prospectProductType);
  updateProspectDiffBadge(data.difficulty);
  updateProspectPanel(data.state);
  syncProspectBar();

  // Apply the saved prospect settings to the UI
  document
    .getElementById("prospectHintsToggle")
    .classList.toggle("on", _prospectSettings.showHints);
  document
    .getElementById("prospectHintsToggle")
    .setAttribute("aria-checked", String(_prospectSettings.showHints));
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
  setIntroVisibility(false);

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
  toggle.setAttribute("aria-checked", String(_prospectSettings.showHints));
  document.getElementById("prospectCoachingSection").style.display =
    _prospectSettings.showHints ? "" : "none";
  localStorage.setItem("prospectSettings", JSON.stringify(_prospectSettings));
}

function toggleProspectSettings() {
  document.getElementById("prospectSettingsBody").classList.toggle("open");
}

function openProspectSetup() {
  // The product dropdown is already rendered by the server, so only sync the UI.
  syncModeChrome();
  document.getElementById("sendBtn").disabled = false;
  document.getElementById("prospectCoachingHint").textContent =
    "Hints will appear after the next prospect reply.";
}

async function selectProspectDifficulty(diff, btn) {
  if (_prospectMode && diff !== _prospectDifficulty) {
    const confirmed = await confirmDialog({
      title: "Change difficulty?",
      body: "Changing difficulty resets the current prospect practice. Continue?",
      confirmLabel: "Reset and change",
    });
    if (!confirmed) return;
    _prospectDifficulty = diff;
    document
      .querySelectorAll(".prospect-diff-btn")
      .forEach((b) => b.classList.toggle("selected", b.dataset.diff === diff));
    resetProspectSession();
    return;
  }
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

  const transactionalSelect = document.getElementById(
    "prospectTransactionalSelect",
  );
  const consultativeSelect = document.getElementById(
    "prospectConsultativeSelect",
  );
  const product =
    transactionalSelect?.value && transactionalSelect.value !== "default"
      ? transactionalSelect.value
      : consultativeSelect?.value && consultativeSelect.value !== "default"
        ? consultativeSelect.value
        : "default";
  _prospectProductType = product;
  syncProspectProductSelects(product);

  try {
    const response = await fetch("/api/prospect/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        difficulty: _prospectDifficulty,
        product_type: product,
      }),
    });
    const data = await response.json();

    if (data.error) {
      showToast(data.error, "error");
      startBtn.disabled = false;
      startBtn.textContent = "Start prospect practice";
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
    // Re-enable the start/exit button after the UI is updated
    startBtn.disabled = false;
    return; // button is now "Exit Prospect"
  } catch (e) {
    showToast("Failed to start prospect mode", "error");
  }
  startBtn.disabled = false;
  startBtn.textContent = "Start prospect practice";
}

/* Mobile: the panel collapses to one bar; this keeps its label current. */
function syncProspectBar() {
  const name = document.getElementById("prospectName").textContent;
  const pct = document.getElementById("prospectReadinessVal").textContent;
  document.getElementById("prospectBarLabel").textContent =
    `Buyer: ${name} · ${pct} ready`;
}

function toggleProspectBar() {
  const open = document
    .getElementById("prospectPanel")
    .classList.toggle("bar-open");
  document
    .getElementById("prospectBarToggle")
    .setAttribute("aria-expanded", open ? "true" : "false");
}

function endProspectMode() {
  try {
    if (_prospectMode && _prospectSessionId) {
      // Best-effort server reset; keep cleaning up the UI even if it fails
      fetch("/api/prospect/reset", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Session-ID": _prospectSessionId,
        },
      }).catch(() => {});
    }
  } finally {
    // Restore the client UI even if the network call fails
    clearProspectSessionState();
    try {
      history.replaceState(null, "", "/");
    } catch (e) {}

    // Hide prospect panel safely
    closeAllPanels();

    // Restore header buttons safely
    const trainingBtn = document.getElementById("trainingToggleBtn");
    const quizBtn = document.getElementById("quizToggleBtn");
    const startBtn = document.getElementById("prospectStartBtn");
    if (trainingBtn) trainingBtn.style.display = "";
    if (quizBtn) quizBtn.style.display = "";
    if (startBtn) {
      startBtn.textContent = "Start prospect practice";
      startBtn.onclick = startProspectMode;
      startBtn.disabled = false;
    }

    // Clear chat and reinit normal mode
    const chatContainer = document.getElementById("chatContainer");
    if (chatContainer) chatContainer.innerHTML = "";
    userTurnIndex = 0;
    setIntroVisibility(false);
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

  /* Colour comes from the tokens via a class, and is always paired with a word:
     a bar that only changes colour says nothing to a colour-blind learner. */
  const band =
    readiness < 30 ? "low" : readiness < 60 ? "mid" : "high";
  fill.className = "prospect-readiness-fill readiness-" + band;
  document.getElementById("prospectReadinessState").textContent = {
    low: "At risk",
    mid: "Warming up",
    high: "Ready",
  }[band];

  document.getElementById("prospectReadinessVal").textContent = readiness + "%";
  syncProspectBar();
  const turns = state.turn_count || 0;
  const max = _prospectMaxTurns;
  document.getElementById("prospectTurnCount").textContent = max
    ? `${turns} / ${max}`
    : turns;
}

function addProspectMessage(text, sender, metrics = null) {
  appendChatMessage(text, sender, metrics, { updateCache: false });
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
    '<div class="message-bubble loading-note">Generating evaluation...</div>';
  container.appendChild(loadingMsg);
  container.scrollTop = container.scrollHeight;

  try {
    const response = await fetch("/api/prospect/evaluate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": _prospectSessionId,
      },
    });
    const data = await response.json();
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
          <h2 id="evalHeading" class="prospect-eval-title">How that session went</h2>
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
          <div class="prospect-eval-actions">
            <button class="review-open-btn" onclick="openSessionReview(this)">Walk it back</button>
            <button class="prospect-try-again-btn" onclick="tryAgainProspect()">Try again</button>
          </div>
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
  overlay.className = "review-overlay";
  const card = document.createElement("div");
  card.className = "prospect-evaluation eval-card";
  card.innerHTML = html;
  overlay.appendChild(card);
  overlay.onclick = (e) => {
    if (e.target === overlay) closeDialog(overlay);
  };
  openDialog(overlay, card, "evalHeading");
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
  closeDialog(document.getElementById("prospectEvalModal"));

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
  closeAllPanels();

  // Re-enable send
  document.getElementById("sendBtn").disabled = false;

  // Restore start button
  const startBtn = document.getElementById("prospectStartBtn");
  startBtn.textContent = "Start prospect practice";
  startBtn.onclick = startProspectMode;

  // Open setup again
  openProspectSetup();
}

