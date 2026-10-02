/* ---------------------------------------------------------------------------
 * Session review: walk the conversation back, and say a turn differently.
 * The buyer replies for real from that point, so a redo is practice, not a
 * description of what you should have said.
 * ------------------------------------------------------------------------- */

function ratingDots(rating) {
  let dots = "";
  for (let i = 1; i <= 5; i++) {
    dots += `<span class="review-dot${i <= rating ? " on" : ""}"></span>`;
  }
  /* role="img" + a label, so the dots are read out rather than being a row of
     shapes a screen reader skips. */
  return `<span class="review-rating" role="img" aria-label="Rated ${rating} out of 5">${dots}</span>`;
}

function buildReviewTurnHTML(turn, isPivotal) {
  const change = turn.readiness_change;
  const drift =
    change === 0
      ? ""
      : `<span class="review-drift ${change > 0 ? "up" : "down"}">${
          change > 0 ? "+" : ""
        }${Math.round(change * 100)}% interest</span>`;

  const reasons = turn.reasons.length
    ? `<ul class="review-reasons">${turn.reasons
        .map((r) => `<li>${escapeHtml(r)}</li>`)
        .join("")}</ul>`
    : `<p class="review-reasons-empty">Nothing here moved them either way.</p>`;

  const redo = isPivotal
    ? `<div class="review-redo" id="reviewRedo${turn.turn}">
         <button class="review-redo-btn" onclick="startRedo(${turn.turn})">Say this differently</button>
       </div>`
    : "";

  return `
    <li class="review-turn${isPivotal ? " pivotal" : ""}">
      <div class="review-turn-head">
        <span class="review-turn-no">Turn ${turn.turn}</span>
        ${ratingDots(turn.rating)}
        ${drift}
      </div>
      <p class="review-said"><span class="review-who">You</span>${escapeHtml(turn.seller)}</p>
      ${turn.buyer ? `<p class="review-said buyer"><span class="review-who">Buyer</span>${escapeHtml(turn.buyer)}</p>` : ""}
      ${reasons}
      ${redo}
    </li>`;
}

function buildReviewHTML(data) {
  const pivotal = new Set(data.pivotal_turns || []);
  const summary = data.summary || {};

  if (!data.turns || !data.turns.length) {
    return `<p class="review-empty">There are no turns to review yet.</p>`;
  }

  const intro = pivotal.size
    ? `${pivotal.size} turn${pivotal.size > 1 ? "s" : ""} cost you ground. Try ${
        pivotal.size > 1 ? "them" : "it"
      } again below and see what they say.`
    : "Nothing here lost you ground. Good session.";

  return `
    <div class="review-head">
      <h3 id="reviewHeading">Walk it back</h3>
      <p class="review-intro">${intro}</p>
      <p class="review-stats">${summary.turn_count} turns &middot; average ${summary.average_rating} out of 5</p>
    </div>
    <ol class="review-turns">
      ${data.turns.map((t) => buildReviewTurnHTML(t, pivotal.has(t.turn))).join("")}
    </ol>`;
}

async function openSessionReview(trigger) {
  if (!_prospectSessionId) return;
  setTriggerBusy(trigger, true, "Opening...");

  try {
    const response = await fetch("/api/prospect/review", {
      headers: { "X-Session-ID": _prospectSessionId },
    });
    const data = await response.json();
    if (!data.success) {
      if (handleProspectSessionError(data)) return;
      showReviewOverlay(reviewErrorHTML(data.error));
      return;
    }
    showReviewOverlay(buildReviewHTML(data));
  } catch (e) {
    showReviewOverlay(reviewErrorHTML(String(e)));
  } finally {
    setTriggerBusy(trigger, false);
  }
}

function reviewErrorHTML(detail) {
  return `<h3 id="reviewHeading" class="review-heading">Walk it back</h3>
    <p class="review-redo-error">Couldn't open the review. ${escapeHtml(detail || "")}</p>
    <button class="review-redo-btn" onclick="closeSessionReview(); openSessionReview();">Try again</button>`;
}

function setTriggerBusy(button, busy, label) {
  /* A button that does nothing visible for a second reads as broken. Triggers
     here range from a plain button to a card with a heading and a description,
     so the whole of the trigger's markup is put back, not just its text. */
  if (!button) return;
  if (busy) {
    if (button.dataset.idleMarkup === undefined) {
      button.dataset.idleMarkup = button.innerHTML;
    }
    button.textContent = label || "Loading...";
  } else if (button.dataset.idleMarkup !== undefined) {
    button.innerHTML = button.dataset.idleMarkup;
    delete button.dataset.idleMarkup;
  }
  button.disabled = busy;
  button.setAttribute("aria-busy", busy ? "true" : "false");
}

function showReviewOverlay(html) {
  closeSessionReview();
  const overlay = document.createElement("div");
  overlay.id = "sessionReviewOverlay";
  overlay.className = "review-overlay";
  overlay.innerHTML = `<div class="review-card">
      <button class="review-close" onclick="closeSessionReview()" aria-label="Close">&times;</button>
      <div id="reviewBody">${html}</div>
    </div>`;
  overlay.onclick = (e) => {
    if (e.target === overlay) closeSessionReview();
  };
  openDialog(overlay, overlay.querySelector(".review-card"), "reviewHeading");
}

function closeSessionReview() {
  closeDialog(document.getElementById("sessionReviewOverlay"));
}

function startRedo(turn, draft) {
  const slot = document.getElementById("reviewRedo" + turn);
  if (!slot) return;
  const lost = document.querySelectorAll(".review-turns > li").length - turn;
  const warning =
    lost > 0
      ? `<p class="review-redo-warning">Saying this differently replaces the ${lost}
         turn${lost === 1 ? "" : "s"} that came after it, and
         ${lost === 1 ? "it can't" : "they can't"} be brought back.</p>`
      : "";
  slot.innerHTML = `
    ${warning}
    <label class="review-redo-label" for="reviewRedoInput${turn}">What would you say instead?</label>
    <textarea id="reviewRedoInput${turn}" class="review-redo-input" rows="2">${escapeHtml(draft || "")}</textarea>
    <button class="review-redo-btn" onclick="submitRedo(${turn})">Try it</button>`;
  const input = document.getElementById("reviewRedoInput" + turn);
  if (input) input.focus();
}

let _redoDraft = "";

async function submitRedo(turn) {
  const input = document.getElementById("reviewRedoInput" + turn);
  const slot = document.getElementById("reviewRedo" + turn);
  if (!input || !slot) return;

  const message = input.value.trim();
  if (!message) {
    input.focus();
    return;
  }
  _redoDraft = message;

  slot.innerHTML = `<p class="review-redo-waiting" aria-live="polite">Seeing how they respond...</p>`;

  try {
    const response = await fetch("/api/prospect/redo", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Session-ID": _prospectSessionId,
      },
      body: JSON.stringify({ turn: turn, message: message }),
    });
    const data = await response.json();

    if (!data.success) {
      slot.innerHTML = `<p class="review-redo-error">${escapeHtml(data.error || "That didn't work.")}</p>
        <button class="review-redo-btn" onclick="startRedo(${turn}, _redoDraft)">Try again</button>`;
      return;
    }

    slot.innerHTML = `
      <div class="review-redo-result">
        <p class="review-said"><span class="review-who">You</span>${escapeHtml(message)}</p>
        <p class="review-said buyer"><span class="review-who">Buyer</span>${escapeHtml(data.message)}</p>
        <p class="review-redo-note">The conversation now continues from here.</p>
      </div>`;
    markTurnsAfterRedoAsGone(turn);
  } catch (e) {
    slot.innerHTML = `<p class="review-redo-error">${escapeHtml(String(e))}</p>
      <button class="review-redo-btn" onclick="startRedo(${turn}, _redoDraft)">Try again</button>`;
  }
}

function markTurnsAfterRedoAsGone(turn) {
  /* Rewinding drops everything after this turn, so the ones still listed below
     are no longer part of the conversation. Leaving them looking live would be
     the review telling the learner something untrue. */
  const list = document.querySelector(".review-turns");
  if (!list) return;

  let found = false;
  let replaced = 0;
  for (const item of list.querySelectorAll(".review-turn")) {
    if (found) {
      item.classList.add("superseded");
      const redo = item.querySelector(".review-redo");
      if (redo) redo.remove();
      replaced += 1;
    }
    if (item.querySelector("#reviewRedo" + turn)) found = true;
  }

  if (replaced && !list.querySelector(".review-superseded-note")) {
    const note = document.createElement("li");
    note.className = "review-superseded-note";
    note.textContent =
      "The turns below came after the one you changed, so they are no longer part of this conversation.";
    const firstGone = list.querySelector(".review-turn.superseded");
    list.insertBefore(note, firstGone);
  }
}

