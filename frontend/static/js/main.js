window.addEventListener("DOMContentLoaded", () => {
  clearStaleOverlayState();
  const ta = document.getElementById("messageInput");
  ta.addEventListener("input", () => autoResizeTextarea(ta));
  autoResizeTextarea(ta);
  speechRecognizer = new SpeechRecognizer();
  setSidebarTab(_sidebarTab);
  updateWorkflowProgress();

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
  setTrainingPanelEmptyState();

  if (isDedicatedProspectPage()) {
    openProspectSetup();
  } else {
    initChatbot();
    // Restore training panel open state
    if (localStorage.getItem("trainingPanelOpen") === "true") {
      toggleTrainingPanel();
    }
  }

  window.addEventListener("resize", syncPanelShellState);

  document.addEventListener("click", (event) => {
    const target = event.target;
    if (
      !target.closest(".overflow-menu") &&
      !target.closest("#feedbackDropdown") &&
      !target.closest(".feedback-pill")
    ) {
      closeResetMenu();
      if (!target.closest("#feedbackDropdown")) {
        document.getElementById("feedbackDropdown")?.classList.remove("open");
      }
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeResetMenu();
      closeSessionReview();
      closeDialog(document.getElementById("prospectEvalModal"));
      document.getElementById("feedbackDropdown")?.classList.remove("open");
    }
  });

  syncPanelShellState();
});

// Page Load Initialization
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    initTtsSpeedControl();
  });
} else {
  // DOM is already loaded
  initTtsSpeedControl();
}

