/* =========================================================================
   Al Rayan — scroll-scrubbed silk background.
   Draws a 20-frame fabric sequence onto a fixed full-viewport canvas and
   advances the frame with the page's scroll progress (0% → frame 1,
   100% → frame 20). Cover-fits each frame and honours reduced-motion.
   ========================================================================= */
(function () {
  var canvas = document.getElementById('silk-bg');
  if (!canvas || !canvas.getContext) return;

  var ctx = canvas.getContext('2d');
  var FRAME_COUNT = 20;
  var base = canvas.getAttribute('data-frame-url') || '';
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var frames = [];
  var current = -1;

  function pad(n) { return ('00' + n).slice(-3); }

  // Cover-fit the frame to the viewport, centred.
  function draw(index, force) {
    var img = frames[index];
    if (!img || !img.complete || !img.naturalWidth) return;
    if (index === current && !force) return;
    current = index;

    var cw = canvas.width, ch = canvas.height;
    var iw = img.naturalWidth, ih = img.naturalHeight;
    var scale = Math.max(cw / iw, ch / ih);
    var dw = iw * scale, dh = ih * scale;
    ctx.clearRect(0, 0, cw, ch);
    ctx.drawImage(img, (cw - dw) / 2, (ch - dh) / 2, dw, dh);
  }

  function resize() {
    var w = window.innerWidth, h = window.innerHeight;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    draw(current < 0 ? 0 : current, true);
  }

  function frameFromScroll() {
    var doc = document.documentElement;
    var max = doc.scrollHeight - window.innerHeight;
    var p = max > 0 ? window.scrollY / max : 0;
    if (p < 0) p = 0; else if (p > 1) p = 1;
    return Math.min(FRAME_COUNT - 1, Math.floor(p * (FRAME_COUNT - 1) + 1e-4));
  }

  var ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(function () {
      draw(frameFromScroll());
      ticking = false;
    });
  }

  // Preload every frame; draw the first one as soon as it lands.
  for (var i = 1; i <= FRAME_COUNT; i++) {
    (function (idx) {
      var img = new Image();
      img.onload = function () {
        if (idx === 0) draw(0, true);
      };
      img.src = base + pad(idx + 1) + '.jpg';
      frames[idx] = img;
    })(i - 1);
  }

  window.addEventListener('resize', resize, { passive: true });
  resize();

  var reduce = window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduce) {
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
})();
