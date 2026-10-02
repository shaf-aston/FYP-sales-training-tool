// Keep the selected training answer style in sync with local storage.
let trainingStyle = localStorage.getItem("trainingStyle") || "tactical";

function changeTrainingStyle(nextStyle) {
  trainingStyle = nextStyle;
  localStorage.setItem("trainingStyle", nextStyle);
}

// Tools dropdown moved to Sidebar

// Exclusive Panel Management
function updateToolCardStates() {
  document
    .getElementById("trainingToggleBtn")
    ?.classList.toggle(
      "active",
      document.getElementById("trainingPanel")?.classList.contains("open"),
    );
  document
    .getElementById("quizToggleBtn")
    ?.classList.toggle(
      "active",
      document.getElementById("quizPanel")?.classList.contains("open"),
    );
}

function isMobilePanelLayout() {
  return window.matchMedia("(max-width: 860px)").matches;
}

function syncPanelShellState() {
  const container = document.querySelector(".container");
  const trainingOpen = document
    .getElementById("trainingPanel")
    ?.classList.contains("open");
  const quizOpen = document
    .getElementById("quizPanel")
    ?.classList.contains("open");
  const prospectOpen = document
    .getElementById("prospectPanel")
    ?.classList.contains("open");

  container?.classList.toggle("panel-open", !!trainingOpen);
  container?.classList.toggle("quiz-panel-open", !!quizOpen);
  container?.classList.toggle("prospect-panel-open", !!prospectOpen);

  const anyPanelOpen = !!(trainingOpen || quizOpen || prospectOpen);
  const lockBody = anyPanelOpen && isMobilePanelLayout();
  document.body.classList.toggle("panel-open", lockBody);
  document.body.style.overflow = lockBody ? "hidden" : "";

  updateToolCardStates();
}

function closePanelStorageFlags() {
  localStorage.setItem("trainingPanelOpen", "false");
  localStorage.setItem("quizPanelOpen", "false");
}

function setSidebarTab(tabName) {
  _sidebarTab = tabName;
  localStorage.setItem("sidebarTab", tabName);
  document.querySelectorAll(".sidebar-tab").forEach((tab) => {
    const on = tab.dataset.sidebarTab === tabName;
    tab.classList.toggle("active", on);
    tab.setAttribute("aria-selected", on ? "true" : "false");
    tab.tabIndex = on ? 0 : -1;
  });
  document.querySelectorAll(".sidebar-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.dataset.sidebarPanel === tabName);
  });
}

function handleSidebarTabKey(event) {
  /* Arrow keys move between tabs (WAI-ARIA tabs pattern); only the active tab
     is in the Tab order. */
  const keys = { ArrowRight: 1, ArrowLeft: -1 };
  const step = keys[event.key];
  const home = event.key === "Home" ? 0 : event.key === "End" ? -1 : null;
  if (!step && home === null) return;
  const tabs = [...document.querySelectorAll(".sidebar-tab")];
  const i = tabs.indexOf(document.activeElement);
  if (i < 0) return;
  event.preventDefault();
  const next = step
    ? tabs[(i + step + tabs.length) % tabs.length]
    : tabs.at(home);
  setSidebarTab(next.dataset.sidebarTab);
  next.focus();
}

function closeAllPanels() {
  const container = document.querySelector(".container");
  ["trainingPanel", "quizPanel", "prospectPanel"].forEach((panelId) => {
    document.getElementById(panelId)?.classList.remove("open");
  });
  closePanelStorageFlags();
  container?.classList.remove(
    "panel-open",
    "quiz-panel-open",
    "prospect-panel-open",
  );
  syncPanelShellState();
}

function toggleTrainingPanel() {
  const panel = document.getElementById("trainingPanel");
  const willOpen = !panel.classList.contains("open");
  if (willOpen) {
    closeAllPanels();
    panel.classList.add("open");
    setSidebarTab("tools");
  } else {
    panel.classList.remove("open");
  }
  localStorage.setItem("trainingPanelOpen", willOpen);
  syncPanelShellState();
}

function updateTrainingPanel(training) {
  const sections = [
    document.querySelector(".training-section--action"),
    document.querySelector(".training-section--trigger"),
    document.querySelector(".training-section--warning"),
  ];

  if (!training) {
    sections.forEach((section) => section?.classList.add("is-hidden"));
    const whatHappened = document.getElementById("tWhatHappened");
    const nextMove = document.getElementById("tNextMove");
    const watchFor = document.getElementById("tWatchFor");
    if (whatHappened) whatHappened.textContent = "";
    if (nextMove) nextMove.textContent = "";
    if (watchFor) watchFor.innerHTML = "";
    return;
  }

  sections.forEach((section) => section?.classList.remove("is-hidden"));

  const cleanText = (text) => {
    if (!text) return "";
    // strip markdown: bold, italic, numbered lists, bullet points
    let clean = String(text)
      .replace(/\*\*([^*]+)\*\*/g, "$1")
      .replace(/\*([^*]+)\*/g, "$1")
      .replace(/^\d+\.\s+/gm, "")
      .replace(/^[-*]\s+/gm, "")
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
  const watchItems = (training.watch_for || []).slice(0, 2);
  if (!watchItems.length) {
    const li = document.createElement("li");
    li.textContent = "No risks flagged yet. Keep the buyer talking.";
    ul.appendChild(li);
    return;
  }
  watchItems.forEach((tip) => {
    const li = document.createElement("li");
    li.innerHTML = cleanText(tip);
    ul.appendChild(li);
  });

  if (
    shouldShowAutoCoachHints() &&
    !document.getElementById("trainingPanel")?.classList.contains("open") &&
    training.next_move
  ) {
    const nextMove = String(training.next_move).replace(/\s+/g, " ").trim();
    if (nextMove && nextMove !== _lastTrainingHintToast) {
      _lastTrainingHintToast = nextMove;
      showToast(`Coach hint: ${nextMove.slice(0, 80)}`, "info");
    }
  }
}

function setTrainingPanelEmptyState() {
  [
    document.querySelector(".training-section--action"),
    document.querySelector(".training-section--trigger"),
    document.querySelector(".training-section--warning"),
  ].forEach((section) => section?.classList.add("is-hidden"));

  const whatHappened = document.getElementById("tWhatHappened");
  const nextMove = document.getElementById("tNextMove");
  const watchFor = document.getElementById("tWatchFor");
  if (whatHappened) whatHappened.textContent = "";
  if (nextMove) nextMove.textContent = "";
  if (watchFor) watchFor.innerHTML = "";
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
  const willOpen = !panel.classList.contains("open");
  closeAllPanels();
  if (willOpen) {
    panel.classList.add("open");
    setSidebarTab("tools");
    fetchQuizQuestion();
  }
  localStorage.setItem("quizPanelOpen", willOpen);
  syncPanelShellState();
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
    document.getElementById("quizFeedback").innerHTML =
      '<div class="loading-note" role="alert">Please enter an answer.</div>';
    document.getElementById("quizAnswer").focus();
    return;
  }

  const submitBtn = document.getElementById("quizSubmitBtn");
  const feedbackEl = document.getElementById("quizFeedback");
  submitBtn.disabled = true;
  feedbackEl.innerHTML = '<div class="loading-note">Evaluating...</div>';

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
    // Stage quiz: numeric score with partial credit
    const numScore = Math.round(data.score * 100);
    score = numScore + "%";
    if (numScore >= 100) feedbackClass = "correct";
    else if (numScore >= 50) feedbackClass = "partial";
    else feedbackClass = "incorrect";
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

