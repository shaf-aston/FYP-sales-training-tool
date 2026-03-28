let isTyping = false,
  userTurnIndex = 0,
  sessionId = null;
// Module-level state to avoid circular DOM reads
let _currentStage = "intent";
let _currentStrategy = "—";

// ─── Voice Mode State ─────────────────────────────────────────
// Server-based voice (Deepgram/Groq + Edge TTS) vs browser-based (Web Speech API)
let voiceModeEnabled = false; // Toggle: true = server voice, false = browser speech
let voiceModeInitialized = false;

// ─── Session ─────────────────────────────────────────────────
function getSessionId() {
  if (!sessionId) sessionId = localStorage.getItem("sessionId");
  return sessionId;
}

// ─── localStorage history ─────────────────────────────────────
// Maintains a mirror of the conversation for reload persistence.
// Stored as [{role:"user"|"assistant", content:str}]
let _cachedHistory = [];

function saveHistoryToStorage() {
  localStorage.setItem("chatHistory", JSON.stringify(_cachedHistory));
}

function loadHistoryFromStorage() {
  try {
    return JSON.parse(localStorage.getItem("chatHistory") || "[]");
  } catch {
    return [];
  }
}

function clearStoredHistory() {
  _cachedHistory = [];
  localStorage.removeItem("chatHistory");
  localStorage.removeItem("chatStage");
  localStorage.removeItem("chatStrategy");
}

// ─── Session Expiration Handler ───────────────────────────────
function handleSessionExpired() {
  // Clear all stored data
  localStorage.removeItem("sessionId");
  clearStoredHistory();
  sessionId = null;

  // Clear the chat container
  const container = document.getElementById("chatContainer");
  container.innerHTML = "";

  // Add a notice
  const notice = document.createElement("div");
  notice.className = "edit-divider";
  notice.textContent = "Session expired — conversation has been reset";
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
    localStorage.removeItem("sessionId"); // Clear ghost ID
    clearStoredHistory();
    sessionId = null;
    initChatbot();
    return true;
  }
  return false;
}

// ─── TTS ──────────────────────────────────────────────────────
const tts = {
  speak: (t) =>
    "speechSynthesis" in window &&
    (speechSynthesis.cancel(),
    speechSynthesis.speak(new SpeechSynthesisUtterance(t)),
    true),
  stop: () => "speechSynthesis" in window && speechSynthesis.cancel(),
  isSpeaking: () => "speechSynthesis" in window && speechSynthesis.speaking,
};

// ─── Toast Notifications ──────────────────────────────────────
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

function parsePunctuation(text) {
  return text
    .replace(/ period /g, ". ")
    .replace(/ comma /g, ", ")
    .replace(/ question mark /g, "? ")
    .replace(/ new line /g, "\n");
}

// ─── Message rendering ────────────────────────────────────────
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
  msg.className = `message ${sender}`;

  if (msgIdx !== null && msgIdx !== undefined) {
    msg.setAttribute("data-msg-idx", msgIdx);
  }

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";

  const safeText = text || "";

  if (sender === "bot" && typeof marked !== "undefined") {
    // Use marked.js for bot messages to support full markdown (lists, bold, etc)
    bubble.innerHTML = marked.parse(safeText);
  } else {
    // Fallback / User messages: preserve newlines
    bubble.innerHTML = safeText
      .split("\n")
      .map((l) => {
        const s = document.createElement("span");
        if (sender === "bot") {
          s.innerHTML = parseMarkdown(l);
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
        speechSynthesis.cancel();
        const utter = new SpeechSynthesisUtterance(text);
        btn.classList.add("speaking");
        utter.onend = () => btn.classList.remove("speaking");
        utter.onerror = () => btn.classList.remove("speaking");
        speechSynthesis.speak(utter);
      }
    };
    actions.appendChild(btn);
  } else {
    const btn = Object.assign(document.createElement("button"), {
      className: "edit-btn",
      innerHTML: "✏️ Edit",
    });
    btn.onclick = () => editMessage(msgIdx, text, msg);
    actions.appendChild(btn);
  }

  msg.appendChild(bubble);
  msg.appendChild(actions);

  if (metrics && sender === "bot") {
    const metricsDiv = document.createElement("div");
    metricsDiv.className = "message-metrics";
    let t = `${metrics.latency_ms.toFixed(1)}ms`;
    if (metrics.provider) t += ` • ${metrics.provider}`;
    if (metrics.input_length || metrics.output_length)
      t += ` • ${metrics.input_length}→${metrics.output_length}`;
    metricsDiv.textContent = t;
    msg.appendChild(metricsDiv);
  }

  return msg;
}

// ─── Inline edit → "string of 2 conversations" ───────────────
// Clicking Edit replaces the bubble with an inline textarea.
// On Save: grey out everything from the edited message onward,
// insert a divider, then append the new branch below.
function editMessage(msgIdx, originalText, msgEl) {
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
    ta.remove();
    btnRow.remove();
    bubble.style.display = "";
    actions.style.display = "";
  };

  saveBtn.onclick = () => {
    const newText = ta.value.trim();
    if (!newText || newText === originalText) {
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
          userTurnIndex = container.querySelectorAll(".message.user").length;
          ta.disabled = false;
          saveBtn.disabled = false;
          cancelBtn.disabled = false;
          alert("Edit failed: " + (data.error || "Unknown error"));
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
        saveHistoryToStorage();

        updateSessionUI(data);
      })
      .catch((e) => {
        rollbackEditUI(allMsgs, startIdx);
        ta.disabled = false;
        saveBtn.disabled = false;
        cancelBtn.disabled = false;
        alert("Edit error: " + e);
      });
  };
}

// ─── Init / reload restoration ────────────────────────────────
function initChatbot() {
  const existingId = localStorage.getItem("sessionId");

  fetch("/api/init", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: existingId,
      // provider can also be sent here
      // They fall back to environment variables if not provided
    }),
  })
    .then((r) => r.json())
    .then((data) => {
      if (data.error) {
        alert("Error: " + data.error);
        return;
      }

      sessionId = data.session_id;
      localStorage.setItem("sessionId", sessionId);
      userTurnIndex = 0;

      if (data.history && data.history.length > 0) {
        // Server restored live session
        _cachedHistory = data.history.map((m) => ({
          role: m.role,
          content: m.content,
        }));
        saveHistoryToStorage();
        data.history.forEach((m) =>
          renderMessage(m.content, m.role === "user" ? "user" : "bot"),
        );
        updateStage(data.stage);
        if (data.strategy) {
          updateStrategy(data.strategy);
          localStorage.setItem("chatStrategy", data.strategy);
        }
      } else {
        // New session — check localStorage for visual restore
        const stored = loadHistoryFromStorage();
        if (stored.length > 0) {
          // Server has no live session (restarted), silently reconstruct
          _cachedHistory = stored;
          stored.forEach((m) =>
            renderMessage(m.content, m.role === "user" ? "user" : "bot"),
          );
          const storedStage = localStorage.getItem("chatStage");
          if (storedStage) updateStage(storedStage);
          const storedStrategy = localStorage.getItem("chatStrategy");
          if (storedStrategy) updateStrategy(storedStrategy);

          // Rebuild server session silently (no user-facing message)
          fetch("/api/restore", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              history: stored,
            }),
          })
            .then((r) => r.json())
            .then((d) => {
              if (d.success) {
                sessionId = d.session_id;
                localStorage.setItem("sessionId", sessionId);
                // Stage/strategy already restored — no flicker
              }
            })
            .catch((e) => {
              // Restore failed — user needs to refresh to continue
              console.error("Restore failed:", e);
              const notice = document.createElement("div");
              notice.className = "edit-divider";
              notice.textContent =
                "Connection issue — please refresh to continue";
              notice.style.color = "#d4a373";
              document.getElementById("chatContainer").appendChild(notice);
              document.getElementById("sendBtn").disabled = true;
            });
        } else {
          addMessage(data.message, "bot");
          updateSessionUI(data);
          if (data.strategy) {
            localStorage.setItem("chatStrategy", data.strategy);
          }
        }
      }
    })
    .catch((error) => {
      alert("Error initializing chatbot: " + error);
    });
}

window.addEventListener("DOMContentLoaded", () => {
  initChatbot();
  const ta = document.getElementById("messageInput");
  ta.addEventListener("input", () => autoResizeTextarea(ta));
  speechRecognizer = new SpeechRecognizer();
  // Restore training panel open state
  if (localStorage.getItem("trainingPanelOpen") === "true") {
    document.getElementById("trainingPanel").classList.add("open");
    document.querySelector(".container").classList.add("panel-open");
  }
  // Dev panel keyboard shortcut
  document.addEventListener("keydown", (e) => {
    if (e.ctrlKey && e.shiftKey && e.key === "D") {
      e.preventDefault();
      toggleDevPanel();
    }
  });
});

// ─── renderMessage ────────────────────────────────────────────
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

// ─── addMessage ───────────────────────────────────────────────
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
    saveHistoryToStorage();
  } else {
    // Cache all bot responses (including initial greeting)
    _cachedHistory.push({ role: "assistant", content: text });
    saveHistoryToStorage();
    localStorage.setItem("chatStage", _currentStage);
    localStorage.setItem("chatStrategy", _currentStrategy);
  }
}

// ─── sendMessage ──────────────────────────────────────────────
function sendMessage() {
  // Route to prospect mode if active
  if (_prospectMode) {
    sendProspectMessage();
    return;
  }

  const input = document.getElementById("messageInput");
  const message = input.value.trim();
  if (!message || isTyping) return;

  addMessage(message, "user");
  input.value = "";
  autoResizeTextarea(input);
  showTyping();

  fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Session-ID": getSessionId(),
    },
    body: JSON.stringify({ message }),
  })
    .then((r) => r.json())
    .then((data) => {
      hideTyping();
      if (data.error) {
        // Check if session expired using improved error detection
        if (handleServerSessionError(data)) return;
        addMessage("Error: " + data.error, "bot");
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
    })
    .catch((error) => {
      hideTyping();
      addMessage("Error: " + error, "bot");
    });
}

// ─── Typing indicator ─────────────────────────────────────────
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

// ─── Badge helpers ────────────────────────────────────────────
function updateStage(stage) {
  _currentStage = stage;
  document.getElementById("stageBadge").textContent = stage.toUpperCase();
}

function updateStrategy(strategy) {
  _currentStrategy = strategy;
  document.getElementById("strategyBadge").textContent = strategy.toUpperCase();
}

// Consolidated UI update helper
function updateSessionUI(data) {
  if (data.stage) updateStage(data.stage);
  if (data.strategy) updateStrategy(data.strategy);
  if (data.training) updateTrainingPanel(data.training);
  // Keep dev panel session state in sync if it's open
  if (document.getElementById("devPanel").classList.contains("open")) {
    loadDevState();
  }
}

// Edit rollback helper
function rollbackEditUI(allMsgs, startIdx) {
  allMsgs.slice(startIdx).forEach((el) => el.classList.remove("historical"));
}

// ─── Training panel ───────────────────────────────────────────
function toggleTrainingPanel() {
  const panel = document.getElementById("trainingPanel");
  const container = document.querySelector(".container");
  const open = panel.classList.toggle("open");
  container.classList.toggle("panel-open", open);
  localStorage.setItem("trainingPanelOpen", open);
}

function updateTrainingPanel(training) {
  if (!training) return;

  const render = (text) => {
    if (!text) return "—";
    if (typeof marked !== "undefined") {
      return marked.parse(text);
    }
    return text; // fallback to plain text if marked not loaded
  };

  document.getElementById("tStageGoal").innerHTML = render(training.stage_goal);
  document.getElementById("tWhatBotDid").innerHTML = render(
    training.what_bot_did,
  );
  document.getElementById("tWhereHeading").innerHTML = render(
    training.where_heading,
  );
  document.getElementById("tNextTrigger").innerHTML = render(
    training.next_trigger,
  );

  const ul = document.getElementById("tWatchFor");
  ul.innerHTML = "";
  (training.watch_for || []).forEach((tip) => {
    const li = document.createElement("li");
    li.innerHTML = render(tip);
    ul.appendChild(li);
  });
}

// ─── Training Q&A ─────────────────────────────────────────────
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
    body: JSON.stringify({ question }),
  })
    .then((r) => r.json())
    .then((data) => {
      const raw = data.answer || data.error || "No answer received.";
      if (typeof marked !== "undefined") {
        answer.innerHTML = marked.parse(raw);
      } else {
        answer.innerHTML = raw
          .split("\n")
          .filter((l) => l.trim())
          .map((l) => `<div>${parseMarkdown(l)}</div>`)
          .join("");
      }
      input.disabled = false;
      input.value = "";
      input.focus();
    })
    .catch((e) => {
      answer.textContent = "Error: " + e;
      input.disabled = false;
    });
}

// ─── Quiz Panel ─────────────────────────────────────────────────
let currentQuizType = "stage";

function toggleQuizPanel() {
  const panel = document.getElementById("quizPanel");
  const container = document.querySelector(".container");
  const open = panel.classList.toggle("open");
  container.classList.toggle("quiz-panel-open", open);
  localStorage.setItem("quizPanelOpen", open);

  if (open) {
    fetchQuizQuestion();
  }
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

  fetch(`/api/quiz/question?type=${currentQuizType}`, {
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
    endpoint = "/api/quiz/stage";
  } else if (currentQuizType === "next_move") {
    body = { response: answer };
    endpoint = "/api/quiz/next-move";
  } else {
    body = { explanation: answer };
    endpoint = "/api/quiz/direction";
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

  // For stage quiz, show expected answer
  if (data.expected) {
    html += `<div class="quiz-details"><strong>Expected:</strong> ${escapeHtml(data.expected.stage)} / ${escapeHtml(data.expected.strategy)}</div>`;
  }

  html += "</div>";
  feedbackEl.innerHTML = html;
}

// ─── Textarea auto-resize ─────────────────────────────────────
function autoResizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = Math.min(el.scrollHeight, 120) + "px";
}

// ─── Key handler ──────────────────────────────────────────────
// Enter = send, Shift+Enter = newline (default textarea behaviour)
function handleKeyDown(event) {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
  // Shift+Enter falls through — browser inserts newline naturally
}

// ─── Reset ───────────────────────────────────────────────────
function resetChat() {
  if (!confirm("Reset conversation? This will clear all history.")) return;

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
        localStorage.removeItem("sessionId");
        sessionId = null;
        updateStage("intent");
        updateStrategy("—");
        initChatbot();
      }
    })
    .catch((error) => alert("Error resetting chat: " + error));
}

// ─── Dev Panel ───────────────────────────────────────────────
let _devConfig = null;
let _devPromptText = "";

function toggleDevPanel() {
  const panel = document.getElementById("devPanel");
  const btn = document.getElementById("devToggleBtn");
  const open = panel.classList.toggle("open");
  btn.classList.toggle("active", open);
  if (open) {
    loadDevState();
    loadDevConfig();
  }
}

function dpToast(msg, duration = 1800) {
  const t = document.getElementById("dp-toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), duration);
}

async function loadDevState() {
  const sid = getSessionId();
  if (!sid) {
    document.getElementById("dp-s-strategy").textContent = "no session";
    return;
  }
  try {
    const r = await fetch("/api/summary", { headers: { "X-Session-ID": sid } });
    const d = await r.json();
    if (!d.success) return;
    const s = d.summary;
    document.getElementById("dp-s-strategy").textContent = s.flow_type || "—";
    document.getElementById("dp-s-stage").textContent = s.current_stage || "—";
    document.getElementById("dp-s-stageTurns").textContent =
      s.stage_turn_count ?? "—";
    document.getElementById("dp-s-totalTurns").textContent =
      s.total_turns ?? "—";
    document.getElementById("dp-s-provider").textContent = s.provider || "—";
    document.getElementById("dp-s-model").textContent = s.model || "—";
    renderStageButtons(s.flow_type, s.current_stage);
  } catch (e) {
    /* silently ignore */
  }
}

function renderStageButtons(flowType, currentStage) {
  const stageMap = {
    intent: ["intent"],
    consultative: ["intent", "logical", "emotional", "pitch", "objection"],
    transactional: ["intent", "pitch", "objection"],
  };
  const stages = stageMap[flowType] || [];
  const container = document.getElementById("dp-stage-btns");
  container.innerHTML = "";
  stages.forEach((s) => {
    const btn = document.createElement("button");
    btn.className = "dp-stage-btn" + (s === currentStage ? " current" : "");
    btn.textContent = s;
    btn.onclick = () => devJumpStage(s);
    container.appendChild(btn);
  });
  if (!stages.length) container.textContent = "No stages (no session)";
}

async function devJumpStage(stage) {
  const sid = getSessionId();
  if (!sid) return;
  try {
    const r = await fetch("/api/debug/stage", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-ID": sid },
      body: JSON.stringify({ stage }),
    });
    const d = await r.json();
    if (!d.success) {
      dpToast("Error: " + (d.error || "failed"));
      return;
    }
    updateStage(d.stage);
    updateStrategy(d.strategy);
    await loadDevState();
    dpToast("Jumped → " + stage.toUpperCase());
  } catch (e) {
    dpToast("Error: " + e);
  }
}

async function loadDevConfig() {
  if (_devConfig) {
    populateDevConfig(_devConfig);
    return;
  }
  try {
    const r = await fetch("/api/debug/config");
    _devConfig = await r.json();
    populateDevConfig(_devConfig);
  } catch (e) {
    /* silently ignore */
  }
}

function populateDevConfig(cfg) {
  const pSel = document.getElementById("dp-product");
  pSel.innerHTML = '<option value="">Default (auto-strategy)</option>';
  (cfg.products || []).forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.id + "  (" + p.strategy + ")";
    pSel.appendChild(opt);
  });

  const prvSel = document.getElementById("dp-provider-sel");
  prvSel.innerHTML = "";
  (cfg.providers || ["groq"]).forEach((p) => {
    const opt = document.createElement("option");
    opt.value = p;
    opt.textContent = p;
    if (p === "groq") opt.selected = true;
    prvSel.appendChild(opt);
  });
}

async function devFetchPrompt() {
  const sid = getSessionId();
  if (!sid) {
    dpToast("No active session");
    return;
  }
  document.getElementById("dp-prompt-pre").textContent = "Fetching…";
  document.getElementById("dp-prompt-wrap").style.display = "block";
  document.getElementById("dp-copy-btn").style.display = "none";
  try {
    const r = await fetch("/api/debug/prompt", {
      headers: { "X-Session-ID": sid },
    });
    const d = await r.json();
    if (d.error) {
      document.getElementById("dp-prompt-pre").textContent =
        "Error: " + d.error;
      return;
    }
    _devPromptText = d.prompt;
    document.getElementById("dp-prompt-pre").textContent = d.prompt;
    document.getElementById("dp-copy-btn").style.display = "inline";
  } catch (e) {
    document.getElementById("dp-prompt-pre").textContent = "Error: " + e;
  }
}

function devCopyPrompt() {
  if (!_devPromptText) return;
  navigator.clipboard
    .writeText(_devPromptText)
    .then(() => dpToast("Copied to clipboard"))
    .catch(() => dpToast("Copy failed"));
}

async function devAnalyseMessage() {
  const sid = getSessionId();
  const input = document.getElementById("dp-analyse-input");
  const result = document.getElementById("dp-analyse-result");
  const message = input.value.trim();
  if (!message) return;
  if (!sid) {
    result.textContent = "No active session";
    return;
  }

  result.textContent = "Running…";
  try {
    const r = await fetch("/api/debug/analyse", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Session-ID": sid },
      body: JSON.stringify({ message }),
    });
    const d = await r.json();
    if (d.error) {
      result.textContent = "Error: " + d.error;
      return;
    }
    result.innerHTML = renderAnalysisResult(d);
  } catch (e) {
    result.textContent = "Error: " + e;
  }
}

function renderAnalysisResult(d) {
  const { state, signal_hits, advancement } = d;

  const stateColor = (v) =>
    v === "high" ? "dp-hit" : v === "low" ? "dp-miss" : "";

  // State row
  const stateHtml = `
          <div class="dp-analyse-group">
            <div class="dp-analyse-group-label">State</div>
            <div class="dp-signal-grid">
              <div class="dp-signal-item"><span class="${stateColor(state.intent)}">●</span> intent: <strong>${state.intent}</strong></div>
              <div class="dp-signal-item"><span class="${state.guarded ? "dp-hit" : "dp-miss"}">●</span> guarded: ${state.guarded}</div>
              <div class="dp-signal-item"><span class="${state.decisive ? "dp-hit" : "dp-miss"}">●</span> decisive: ${state.decisive}</div>
              <div class="dp-signal-item"><span class="${state.question_fatigue ? "dp-hit" : "dp-miss"}">●</span> q.fatigue: ${state.question_fatigue}</div>
            </div>
          </div>`;

  // Signals
  const sigLabels = {
    high_intent: "High Intent",
    low_intent: "Low Intent",
    commitment: "Commitment",
    objection: "Objection",
    walking: "Walking Away",
    impatience: "Impatience",
    demands_directness: "Demands Directness",
    direct_info_requests: "Direct Info Req",
    user_consultative_signals: "→ Consultative",
    user_transactional_signals: "→ Transactional",
  };
  const sigItems = Object.entries(sigLabels)
    .map(([k, label]) => {
      const hit = signal_hits[k];
      return `<div class="dp-signal-item"><span class="${hit ? "dp-hit" : "dp-miss"}">${hit ? "✓" : "✗"}</span> <span class="${hit ? "" : "dp-miss"}">${label}</span></div>`;
    })
    .join("");
  const signalsHtml = `
          <div class="dp-analyse-group">
            <div class="dp-analyse-group-label">Signals</div>
            <div class="dp-signal-grid">${sigItems}</div>
          </div>`;

  // Advancement
  const rule = advancement.rule || "none";
  const wa = advancement.would_advance;
  const waClass = wa === null ? "dp-adv-null" : wa ? "dp-adv-yes" : "dp-adv-no";
  const waLabel =
    wa === null
      ? "N/A (terminal stage)"
      : wa
        ? "YES — would advance"
        : "NO — stays in stage";
  const advHtml = `
          <div class="dp-analyse-group">
            <div class="dp-analyse-group-label">Advancement Check</div>
            <div class="dp-adv-box">
              <div>Rule: <span style="color:#8aa080">${rule}</span></div>
              <div>Stage turns: <span style="color:#c8d4c0">${advancement.stage_turns}</span></div>
              <div class="${waClass}" style="margin-top:3px;font-weight:600">${waLabel}</div>
            </div>
          </div>`;

  return stateHtml + signalsHtml + advHtml;
}

async function devApplyReinit() {
  const product = document.getElementById("dp-product").value || null;
  const provider = document.getElementById("dp-provider-sel").value || "groq";
  const forceStrategy =
    document.getElementById("dp-strategy-sel").value || null;

  // Reset current session silently
  const sid = getSessionId();
  if (sid) {
    try {
      await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Session-ID": sid },
      });
    } catch (e) {
      /* ignore */
    }
  }

  // Clear client state
  document.getElementById("chatContainer").innerHTML = "";
  userTurnIndex = 0;
  clearStoredHistory();
  localStorage.removeItem("sessionId");
  sessionId = null;
  updateStage("intent");
  updateStrategy("—");

  // Reinit with new settings (extend the existing initChatbot flow)
  const body = { provider };
  if (product) body.product_type = product;
  if (forceStrategy) body.force_strategy = forceStrategy;

  try {
    const r = await fetch("/api/init", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await r.json();
    if (data.error) {
      dpToast("Init failed: " + data.error);
      return;
    }

    sessionId = data.session_id;
    localStorage.setItem("sessionId", sessionId);
    userTurnIndex = 0;
    addMessage(data.message, "bot");
    updateSessionUI(data);
    if (data.strategy) localStorage.setItem("chatStrategy", data.strategy);

    await loadDevState();
    dpToast("Reinitialised ✓");
  } catch (e) {
    dpToast("Error: " + e);
  }
}

// ─── Prospect Mode ──────────────────────────────────────────────
let _prospectMode = false;
let _prospectSessionId = null;
let _prospectDifficulty = "medium";
let _prospectSettings = { showHints: false, evalDisplay: "inline" };

// Load prospect settings from localStorage
try {
  const saved = JSON.parse(localStorage.getItem("prospectSettings") || "{}");
  if (saved.showHints !== undefined)
    _prospectSettings.showHints = saved.showHints;
  if (saved.evalDisplay) _prospectSettings.evalDisplay = saved.evalDisplay;
} catch {}

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
  // Populate product dropdown from debug config
  loadProspectProducts();
  document.getElementById("prospectSetup").classList.add("open");
}

function closeProspectSetup() {
  document.getElementById("prospectSetup").classList.remove("open");
}

function selectProspectDifficulty(diff, btn) {
  _prospectDifficulty = diff;
  document
    .querySelectorAll(".prospect-diff-btn")
    .forEach((b) => b.classList.remove("selected"));
  btn.classList.add("selected");
}

async function loadProspectProducts() {
  const sel = document.getElementById("prospectProductSelect");
  if (sel.options.length > 1) return; // already loaded
  try {
    const r = await fetch("/api/debug/config");
    const cfg = await r.json();
    (cfg.products || []).forEach((p) => {
      if (p.id === "default") return;
      const opt = document.createElement("option");
      opt.value = p.id;
      opt.textContent = p.id.replace(/_/g, " ") + " (" + p.strategy + ")";
      sel.appendChild(opt);
    });
  } catch {
    // Silent — just use default
  }
}

async function startProspectMode() {
  const startBtn = document.getElementById("prospectStartBtn");
  startBtn.disabled = true;
  startBtn.textContent = "Starting...";

  const product = document.getElementById("prospectProductSelect").value;

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
      alert("Error: " + data.error);
      startBtn.disabled = false;
      startBtn.textContent = "Start Practice";
      return;
    }

    _prospectMode = true;
    _prospectSessionId = data.session_id;

    // Close setup overlay
    closeProspectSetup();

    // Hide training/quiz panels
    document.getElementById("trainingPanel").classList.remove("open");
    document.querySelector(".container").classList.remove("panel-open");
    document.getElementById("quizPanel").classList.remove("open");
    document.querySelector(".container").classList.remove("quiz-panel-open");

    // Show prospect panel
    document.getElementById("prospectPanel").classList.add("open");
    document.querySelector(".container").classList.add("prospect-panel-open");

    // Update header badges
    document.getElementById("strategyBadge").textContent = "PROSPECT MODE";
    document.getElementById("stageBadge").textContent =
      _prospectDifficulty.toUpperCase();

    // Hide sales mode buttons, show active prospect indicator
    document.getElementById("trainingToggleBtn").style.display = "none";
    document.getElementById("quizToggleBtn").style.display = "none";
    document.getElementById("prospectToggleBtn").textContent = "Exit Prospect";
    document.getElementById("prospectToggleBtn").onclick = endProspectMode;

    // Update panel info
    document.getElementById("prospectName").textContent = data.persona.name;
    document.getElementById("prospectBackground").textContent =
      data.persona.background;
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

    // Clear chat and show prospect's opening message
    document.getElementById("chatContainer").innerHTML = "";
    userTurnIndex = 0;

    const metrics = {
      latency_ms: data.latency_ms || 0,
      provider: data.provider || "",
      input_length: 0,
      output_length: 0,
    };
    addProspectMessage(data.message, "bot", metrics);
  } catch (e) {
    alert("Error starting prospect mode: " + e);
  }
  startBtn.disabled = false;
  startBtn.textContent = "Start Practice";
}

function endProspectMode() {
  if (_prospectMode && _prospectSessionId) {
    fetch("/api/prospect/reset", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": _prospectSessionId,
      },
    }).catch(() => {});
  }

  _prospectMode = false;
  _prospectSessionId = null;

  // Hide prospect panel
  document.getElementById("prospectPanel").classList.remove("open");
  document.querySelector(".container").classList.remove("prospect-panel-open");

  // Restore header buttons
  document.getElementById("trainingToggleBtn").style.display = "";
  document.getElementById("quizToggleBtn").style.display = "";
  document.getElementById("prospectToggleBtn").textContent = "Prospect Mode";
  document.getElementById("prospectToggleBtn").onclick = openProspectSetup;

  // Restore badges
  const storedStage = localStorage.getItem("chatStage");
  const storedStrategy = localStorage.getItem("chatStrategy");
  if (storedStage) updateStage(storedStage);
  else updateStage("—");
  if (storedStrategy) updateStrategy(storedStrategy);
  else updateStrategy("—");

  // Clear chat and reinit normal mode
  document.getElementById("chatContainer").innerHTML = "";
  userTurnIndex = 0;
  clearStoredHistory();
  localStorage.removeItem("sessionId");
  sessionId = null;
  initChatbot();
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
  document.getElementById("prospectTurnCount").textContent =
    state.turn_count || 0;
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
  const input = document.getElementById("messageInput");
  const message = input.value.trim();
  if (!message || isTyping) return;

  addProspectMessage(message, "user");
  input.value = "";
  autoResizeTextarea(input);
  showTyping();

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
  })
    .then((r) => r.json())
    .then((data) => {
      hideTyping();
      if (data.error) {
        addProspectMessage("Error: " + data.error, "bot");
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
      }

      // Check if session ended
      if (data.ended) {
        handleProspectEnd(data.outcome);
      }
    })
    .catch((e) => {
      hideTyping();
      addProspectMessage("Error: " + e, "bot");
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
      criteriaHtml += `
              <div class="prospect-eval-criterion">
                <div>
                  <div class="prospect-eval-criterion-name">${name.replace(/_/g, " ")}</div>
                  <div class="prospect-eval-criterion-feedback">${info.feedback || ""}</div>
                </div>
                <div class="prospect-eval-criterion-score">${info.score}%</div>
              </div>`;
    }
  }

  let strengthsHtml = "";
  if (data.strengths && data.strengths.length) {
    strengthsHtml = `<div class="prospect-eval-list">
            <div class="prospect-eval-list-title">Strengths</div>
            <ul>${data.strengths.map((s) => `<li>${s}</li>`).join("")}</ul>
          </div>`;
  }

  let improvementsHtml = "";
  if (data.improvements && data.improvements.length) {
    improvementsHtml = `<div class="prospect-eval-list">
            <div class="prospect-eval-list-title">Areas for Improvement</div>
            <ul>${data.improvements.map((s) => `<li>${s}</li>`).join("")}</ul>
          </div>`;
  }

  return `
          <div class="prospect-eval-header">
            <div class="prospect-eval-score">${data.overall_score || 0}%</div>
            <div class="prospect-eval-grade ${gradeClass}">${data.grade || "?"}</div>
          </div>
          <div class="prospect-eval-outcome ${outcomeClass}">
            ${data.outcome === "sold" ? "Sale Made" : data.outcome === "walked" ? "Prospect Walked Away" : "Incomplete"}
          </div>
          <div class="prospect-eval-criteria">${criteriaHtml}</div>
          ${strengthsHtml}
          ${improvementsHtml}
          ${data.summary ? `<div class="prospect-eval-summary">${data.summary}</div>` : ""}
          <button class="prospect-try-again-btn" onclick="tryAgainProspect()">Try Again</button>
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
  body.innerHTML = `<div style="padding:16px">${html}</div>`;
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
  _prospectSessionId = null;
  _prospectMode = false;

  // Restore prospect panel body
  document.getElementById("prospectPanel").classList.remove("open");
  document.querySelector(".container").classList.remove("prospect-panel-open");

  // Re-enable send
  document.getElementById("sendBtn").disabled = false;

  // Open setup again
  openProspectSetup();
}

// ─── Speech module ────────────────────────────────────────────
let speechRecognizer;

function toggleMic() {
  const micBtn = document.getElementById("micBtn");
  const input = document.getElementById("messageInput");

  // Use server-based voice mode if enabled
  if (voiceModeEnabled) {
    toggleServerVoiceMode(micBtn, input);
    return;
  }

  // Fallback to browser-based speech recognition
  if (!speechRecognizer) {
    alert("Speech module loading...");
    return;
  }

  if (speechRecognizer.isRecording) {
    speechRecognizer.stop();
    return;
  }

  micBtn.classList.add("recording");
  micBtn.innerHTML = "⏹";
  let baseText = input.value;

  speechRecognizer.start(
    (text) => {
      baseText += parsePunctuation(text);
      input.value = baseText;
      autoResizeTextarea(input);
      input.focus();
    },
    (text) => {
      input.value = baseText + text;
    },
    () => {
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "🎤";
      input.focus();
    },
    (err) => {
      console.warn("Mic Error:", err);
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "🎤";
    },
  );
}

/**
 * Server-based voice mode: Record audio → Deepgram/Groq → LLM → Edge TTS
 */
async function toggleServerVoiceMode(micBtn, input) {
  const vm = getVoiceMode();

  // Initialize on first use
  if (!voiceModeInitialized) {
    micBtn.innerHTML = "⏳";
    const ok = await vm.init();
    if (!ok) {
      micBtn.innerHTML = "🎤";
      alert("Could not access microphone. Please allow microphone access.");
      return;
    }
    voiceModeInitialized = true;

    // Set up callbacks
    vm.onTranscription = (text) => {
      // Add user's transcribed message to chat
      addMessage(text, "user");
      input.value = "";
    };

    vm.onResponse = (data) => {
      // Add bot response with metrics
      const metrics = {
        latency_ms: data.latency?.total_ms || 0,
        provider: data.provider,
        model: data.model,
      };
      addMessage(data.message, "assistant", metrics);

      // Update stage/strategy display
      if (data.stage) updateStage(data.stage);
      if (data.strategy) updateStrategy(data.strategy);

      // Update training panel
      if (data.training) updateTrainingPanel(data.training);
    };

    vm.onError = (err) => {
      console.error("Voice mode error:", err);
      showToast(err, "error");
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "🎤";
    };

    vm.onRecordingStart = () => {
      micBtn.classList.add("recording");
      micBtn.innerHTML = "⏹";
    };

    vm.onRecordingStop = () => {
      micBtn.innerHTML = "⏳"; // Processing indicator
    };

    vm.onAudioPlay = () => {
      // Optional: Visual feedback when bot is speaking
    };

    vm.onAudioEnd = () => {
      micBtn.classList.remove("recording");
      micBtn.innerHTML = "🎤";
    };
  }

  // Toggle recording
  if (vm.isRecording) {
    vm.stopRecording();
  } else {
    vm.startRecording();
  }
}

/**
 * Enable/disable server-based voice mode
 */
function setVoiceMode(enabled) {
  voiceModeEnabled = enabled;
  const btn = document.getElementById("voiceModeBtn");
  const indicator = document.getElementById("voiceModeIndicator");

  if (btn) {
    btn.classList.toggle("active", enabled);
  }
  if (indicator) {
    indicator.textContent = enabled ? "🔊" : "⌨️";
  }

  // Show feedback
  showToast(
    enabled
      ? "Voice Mode enabled (server-based)"
      : "Voice Mode disabled (browser-based)",
    "info",
  );
  console.log(
    "Voice mode:",
    enabled ? "enabled (server)" : "disabled (browser)",
  );
}

/**
 * Toggle voice mode on/off
 */
function toggleVoiceMode() {
  setVoiceMode(!voiceModeEnabled);
}
