/* ---------------------------------------------------------------------------
 * Script drills: recall practice.
 * The line appears with the move missing. You produce it in your head, click to
 * check, then say whether you had it. Missed ones come back sooner.
 * Scheduling lives in this browser only - no account, nothing sent anywhere.
 * ------------------------------------------------------------------------- */

const DRILL_STORE_KEY = "drillSchedule.v1";
const DRILL_INTERVALS_DAYS = [0, 1, 3, 7, 21];
const DAY_MS = 86400000;

function loadDrillSchedule() {
  try {
    return JSON.parse(localStorage.getItem(DRILL_STORE_KEY) || "{}") || {};
  } catch (e) {
    return {};
  }
}

function saveDrillSchedule(schedule) {
  try {
    localStorage.setItem(DRILL_STORE_KEY, JSON.stringify(schedule));
  } catch (e) {
    /* Private window or storage full: drilling still works, it just won't be
       remembered next visit. Not worth interrupting the learner over. */
  }
}

function scheduleDrill(id, gotIt) {
  const schedule = loadDrillSchedule();
  const current = schedule[id] || { level: 0 };
  const level = gotIt
    ? Math.min(current.level + 1, DRILL_INTERVALS_DAYS.length - 1)
    : 0;
  schedule[id] = { level: level, due: Date.now() + DRILL_INTERVALS_DAYS[level] * DAY_MS };
  saveDrillSchedule(schedule);
}

function isDrillDue(id) {
  const entry = loadDrillSchedule()[id];
  return !entry || !entry.due || entry.due <= Date.now();
}

function buildDrillHTML(drill, index) {
  let body = "";
  drill.segments.forEach((segment, i) => {
    body += escapeHtml(segment);
    if (i < drill.answers.length) {
      body += `<button class="drill-blank" id="drillBlank${index}_${i}"
                 onclick="revealBlank(${index}, ${i})"
                 aria-label="Reveal the missing words">&nbsp;?&nbsp;</button>`;
    }
  });

  const gaps = drill.answers.length;
  return `
    <div class="drill-card" id="drillCard${index}">
      <div class="drill-label">
        ${escapeHtml(drill.label)}
        <span class="drill-count" id="drillCount${index}" aria-live="polite">0 of ${gaps} revealed</span>
      </div>
      <p class="drill-line">${body}</p>
      <div class="drill-actions" id="drillActions${index}" aria-live="polite" hidden>
        <span class="drill-ask">Did you have it?</span>
        <button class="drill-got" onclick="gradeDrill(${index}, true)">Yes</button>
        <button class="drill-missed" onclick="gradeDrill(${index}, false)">Not quite</button>
      </div>
    </div>`;
}

let _drills = [];

async function openScriptDrills(trigger) {
  setTriggerBusy(trigger, true, "Opening...");
  try {
    const headers = _prospectSessionId ? { "X-Session-ID": _prospectSessionId } : {};
    const response = await fetch("/api/prospect/drills", { headers: headers });
    const data = await response.json();
    if (!data.success) throw new Error(data.error || "Drills unavailable");

    _drills = data.drills;
    const due = _drills
      .map((d, i) => ({ drill: d, index: i }))
      .filter((item) => isDrillDue(item.drill.id));
    const practising = due.length ? due : _drills.map((d, i) => ({ drill: d, index: i }));

    const note = !_drills.length
      ? "There are no lines to practise yet."
      : due.length
      ? `${due.length} to practise.`
      : "Nothing is due - here they all are anyway.";

    showReviewOverlay(`
      <div class="review-head">
        <h3 id="reviewHeading">Say it from memory</h3>
        <p class="review-intro">Work out the missing part before you click it. ${note}</p>
      </div>
      <div class="drill-list">
        ${practising.map((item) => buildDrillHTML(item.drill, item.index)).join("")}
      </div>`);
  } catch (e) {
    /* Say so. Clicking a button and having nothing happen leaves the learner
       unable to tell a broken screen from an empty one. */
    showReviewOverlay(`
      <div class="review-head">
        <h3 id="reviewHeading">Say it from memory</h3>
        <p class="review-intro">The drills couldn't be loaded just now. Close this and try again.</p>
      </div>`);
  } finally {
    setTriggerBusy(trigger, false);
  }
}

function revealBlank(index, blankIndex) {
  const drill = _drills[index];
  const button = document.getElementById(`drillBlank${index}_${blankIndex}`);
  if (!drill || !button) return;

  const answer = document.createElement("span");
  answer.className = "drill-revealed";
  answer.textContent = drill.answers[blankIndex];
  button.replaceWith(answer);

  const card = document.getElementById(`drillCard${index}`);
  if (!card) return;

  const remaining = card.querySelectorAll(".drill-blank").length;
  const total = drill.answers.length;
  const counter = document.getElementById(`drillCount${index}`);
  if (counter) counter.textContent = `${total - remaining} of ${total} revealed`;

  if (!remaining) {
    const actions = document.getElementById(`drillActions${index}`);
    if (actions) actions.hidden = false;
  }
}

function gradeDrill(index, gotIt) {
  const drill = _drills[index];
  if (!drill) return;
  scheduleDrill(drill.id, gotIt);

  const actions = document.getElementById(`drillActions${index}`);
  if (actions) {
    actions.innerHTML = gotIt
      ? `<span class="drill-done">Kept. Back in a few days.</span>`
      : `<span class="drill-again">Back later today.</span>`;
  }
}

