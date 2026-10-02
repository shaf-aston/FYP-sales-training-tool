// Night-city film: blurred city lights drifting behind the app.
// Drawn live (no video file, no people). Colours and count come from CSS tokens in chat.css.
(function () {
  const canvas = document.getElementById("ambientFilm");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const css = getComputedStyle(document.documentElement);
  const token = (name) => css.getPropertyValue(name).trim();
  const hues = token("--film-hues").split(/\s+/).map(Number);
  const count = Number(token("--film-light-count")) || 0;
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  const lights = Array.from({ length: count }, () => ({
    x: Math.random(),
    y: 0.3 + Math.random() * 0.7,
    r: 10 + Math.random() * 40,
    speed: 0.00015 + Math.random() * 0.0007,
    hue: hues[Math.floor(Math.random() * hues.length)],
    alpha: 0.1 + Math.random() * 0.22,
    phase: Math.random() * 6,
  }));

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = innerWidth * dpr;
    canvas.height = innerHeight * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw(t) {
    const w = innerWidth, h = innerHeight;
    const sky = ctx.createLinearGradient(0, 0, 0, h);
    sky.addColorStop(0, token("--film-sky-top"));
    sky.addColorStop(1, token("--film-sky-bottom"));
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, w, h);
    for (const l of lights) {
      if (!still) l.x = (l.x + l.speed) % 1.1;
      const x = l.x * w, y = l.y * h;
      const a = l.alpha * (0.7 + 0.3 * Math.sin(t / 700 + l.phase));
      const g = ctx.createRadialGradient(x, y, 0, x, y, l.r);
      g.addColorStop(0, `hsla(${l.hue}, 90%, 65%, ${a})`);
      g.addColorStop(1, `hsla(${l.hue}, 90%, 65%, 0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(x, y, l.r, 0, Math.PI * 2);
      ctx.fill();
    }
  }

  function loop(t) {
    if (!document.hidden) draw(t);
    requestAnimationFrame(loop);
  }

  addEventListener("resize", () => { resize(); if (still) draw(0); });
  resize();
  draw(0);
  if (!still) requestAnimationFrame(loop);
})();
