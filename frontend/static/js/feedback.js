// Feedback Widget
let _fbRating = 0;

function toggleFeedback() {
  const dd = document.getElementById("feedbackDropdown");
  closeResetMenu();
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
    const response = await fetch("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        rating: _fbRating || null,
        comment: comment || null,
        page: _prospectMode ? "prospect" : "chat",
      }),
    });
    const result = await response.json();
    if (result.success) {
      const feedbackDropdown = document.getElementById("feedbackDropdown");
      feedbackDropdown.innerHTML =
        '<div class="fb-thanks">Thanks for your feedback!</div>';
      setTimeout(() => {
        feedbackDropdown.classList.remove("open");
        feedbackDropdown.innerHTML = buildFeedbackForm();
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

