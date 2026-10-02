/* "How it works" window and the two keyboard shortcuts ("?" help, "/" message box).
   Opens by itself once per browser; the page works the same when storage is blocked. */

const HELP_SEEN_KEY = "helpSeen";

function openHelp() {
  if (document.getElementById("helpOverlay")) return;
  const overlay = document.createElement("div");
  overlay.id = "helpOverlay";
  overlay.className = "review-overlay";
  overlay.innerHTML = `<div class="review-card help-card">
      <button class="review-close" type="button" aria-label="Close">&times;</button>
      <h2 id="helpHeading">How it works</h2>
      <h3>Two ways to practise</h3>
      <ul class="review-reasons">
        <li><strong>Seller bot:</strong> you are the customer. An AI salesperson talks to you, and you can quiz yourself on what stage the sale is in.</li>
        <li><strong>Prospect practice:</strong> you are the salesperson. An AI buyer answers you.</li>
      </ul>
      <h3>Reading your progress</h3>
      <ul class="review-reasons">
        <li><strong>Buying readiness bar:</strong> how ready the buyer is to buy. Good questions and listening push it up; pushy or vague lines push it down.</li>
        <li><strong>Score:</strong> when you end a practice, it rates the whole conversation out of 100%.</li>
      </ul>
      <h3>Learning from a session</h3>
      <ul class="review-reasons">
        <li><strong>Walk it back:</strong> replay each of your turns with the reasons behind its rating, and redo one.</li>
        <li><strong>Drills:</strong> fill in the missing move in lines from real sales scripts.</li>
        <li><strong>Quiz:</strong> rewrite your weakest turn and see why the new version is better or worse.</li>
      </ul>
      <h3>Keyboard shortcuts</h3>
      <ul class="review-reasons">
        <li><kbd>?</kbd> opens this window</li>
        <li><kbd>/</kbd> jumps to the message box</li>
        <li><kbd>Esc</kbd> closes any open window</li>
      </ul>
    </div>`;
  const card = overlay.querySelector(".review-card");
  const close = () => closeDialog(overlay);
  overlay.querySelector(".review-close").onclick = close;
  overlay.onclick = (e) => {
    if (e.target === overlay) close();
  };
  overlay.addEventListener("dialog-close", () => {
    try {
      localStorage.setItem(HELP_SEEN_KEY, "1");
    } catch (e) {
      /* storage blocked: the window simply shows again next visit */
    }
  });
  openDialog(overlay, card, "helpHeading");
}

function openHelpOnFirstVisit() {
  try {
    if (localStorage.getItem(HELP_SEEN_KEY)) return;
  } catch (e) {
    return; /* cannot remember a visit, so never nag */
  }
  openHelp();
}

document.addEventListener("keydown", (event) => {
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const tag = event.target.tagName;
  if (/^(INPUT|TEXTAREA|SELECT)$/.test(tag) || event.target.isContentEditable) return;
  if (document.querySelector('[role="dialog"]')) return;
  if (event.key === "?") {
    event.preventDefault();
    openHelp();
  } else if (event.key === "/") {
    const box = document.getElementById("messageInput");
    if (box && box.offsetParent !== null) {
      event.preventDefault();
      box.focus();
    }
  }
});

document.addEventListener("DOMContentLoaded", openHelpOnFirstVisit);
