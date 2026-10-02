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

function setFlowControlsEnabled(enabled) {
  [
    "stageSelectMain",
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

  const select = document.getElementById("stageSelectMain");
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
    option.textContent = getStageMeta(normalizedStage).label;
    select.appendChild(option);
  });

  select.value = stages.includes(normalizedSelected) ? normalizedSelected : "";
  select.disabled = stages.length === 0;
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
      if (handleServerSessionError(data, { notify: false })) {
        return [];
      }
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
    // Keep strategy controls usable even if the stage list cannot be loaded.
    setFlowControlsEnabled(Boolean(getSessionId()));
    return [];
  }
}

async function jumpStage(selectId = "stageSelectMain") {
  // Verify session is still active before attempting jump
  if (!getSessionId()) {
    showToast("Session lost - reinitializing...", "info");
    initChatbot();
    return;
  }

  const select = document.getElementById(selectId);
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
    showToast(`Moved to ${getStageMeta(stage).label}`, "success");
  } catch (error) {
    // Recovery may already be in progress after a session-expired response.
    if (!getSessionId()) {
      return;
    }
    showToast(error.message || "Stage jump failed", "error");
  }
}

async function switchStrategy(selectId = "strategySelectMain") {
  // Verify session is still active before attempting switch
  if (!getSessionId()) {
    showToast("Session lost - reinitializing...", "info");
    initChatbot();
    return;
  }

  const select =
    document.getElementById(selectId) ||
    document.getElementById("strategySelectMain");
  const availableStrategies = Array.from(select?.options || [])
    .map((opt) =>
      String(opt?.value || "")
        .trim()
        .toLowerCase(),
    )
    .filter(Boolean);
  let strategy = String(select?.value || "")
    .trim()
    .toLowerCase();

  if (!strategy) {
    strategy =
      availableStrategies.find((option) => option !== _currentStrategy) ||
      availableStrategies[0] ||
      "";
    if (select && strategy) {
      select.value = strategy;
    }
  }

  if (!strategy) {
    showToast("Pick a strategy first", "info");
    return;
  }

  try {
    const data = await requestStrategySwitch(strategy);
    updateSessionUI(data);
    await loadStageOptions();
    showToast(`Approach set to ${getStrategyMeta(strategy).label}`, "success");
  } catch (error) {
    // Recovery may already be in progress after a session-expired response.
    if (!getSessionId()) {
      return;
    }
    syncStrategySelectors(_currentStrategy);
    showToast(error.message || "Strategy switch failed", "error");
  }
}

async function executeFlowVoiceCommand(command) {
  if (!command) return false;

  try {
    if (command.type === "stage") {
      const stageData = await requestStageJump(command.value);
      updateSessionUI(stageData);
      showToast(`Voice: moved to ${getStageMeta(command.value).label}`, "info");
      return true;
    }

    if (command.type === "strategy") {
      const strategyData = await requestStrategySwitch(command.value);
      updateSessionUI(strategyData);
      showToast(
        `Voice: approach set to ${getStrategyMeta(command.value).label}`,
        "info",
      );
      return true;
    }
  } catch (e) {
    showToast("Voice command error: " + e, "error");
  }

  return false;
}

