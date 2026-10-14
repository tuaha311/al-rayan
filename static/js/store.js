/* Floral Finesse storefront — lightweight progressive enhancement.
   Everything here is optional: the store works without JS (plain form posts). */
(function () {
  'use strict';

  function rs(n) {
    return 'Rs ' + Math.round(n).toLocaleString('en-US');
  }

  // --- Auto-dismiss flash messages -------------------------------------
  var flashWrap = document.getElementById('flash-wrap');
  if (flashWrap) {
    setTimeout(function () {
      Array.prototype.forEach.call(flashWrap.children, function (el) {
        el.style.transition = 'opacity .4s, transform .4s';
        el.style.opacity = '0';
        el.style.transform = 'translateX(20px)';
      });
      setTimeout(function () { flashWrap.remove(); }, 450);
    }, 3500);
  }

  // --- Drawers: menu (left) and search (right) ---------------------------
  // Any [data-drawer-open="id"] opens that drawer; the overlay, close buttons
  // and Escape close it. Opening one drawer swaps out whichever is open.
  var overlay = document.querySelector('.ff-overlay');
  var openDrawer = null;
  var opener = null;
  var DRAWER_MS = 500;   // matches the CSS slide transition

  function setOpeners(id, open) {
    document.querySelectorAll('[data-drawer-open="' + id + '"]').forEach(function (b) {
      b.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }

  function closeDrawer(restoreFocus) {
    if (!openDrawer) return;
    var d = openDrawer;
    openDrawer = null;
    d.classList.remove('is-open');
    d.setAttribute('aria-hidden', 'true');
    d.inert = true;
    setOpeners(d.id, false);
    overlay.classList.remove('is-open');
    document.body.classList.remove('has-drawer');
    setTimeout(function () { if (!openDrawer) overlay.hidden = true; }, DRAWER_MS);
    if (restoreFocus && opener) opener.focus();
  }

  function showDrawer(d, trigger) {
    if (openDrawer === d) return;
    // Switching from the menu to search keeps the original trigger for focus.
    if (!openDrawer) opener = trigger;
    closeDrawer(false);
    openDrawer = d;
    overlay.hidden = false;
    d.inert = false;
    d.setAttribute('aria-hidden', 'false');
    setOpeners(d.id, true);
    document.body.classList.add('has-drawer');
    // Let the un-hidden overlay paint once so its fade-in runs.
    requestAnimationFrame(function () {
      overlay.classList.add('is-open');
      d.classList.add('is-open');
    });
    var field = d.querySelector('input[type="search"]');
    setTimeout(function () { (field || d.querySelector('.ff-drawer__close')).focus(); }, 50);
  }

  if (overlay) {
    document.addEventListener('click', function (e) {
      var openBtn = e.target.closest('[data-drawer-open]');
      if (openBtn) {
        var d = document.getElementById(openBtn.getAttribute('data-drawer-open'));
        if (d) { e.preventDefault(); showDrawer(d, openBtn); }
        return;
      }
      if (e.target.closest('[data-drawer-close]')) closeDrawer(true);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && openDrawer) closeDrawer(true);
    });
    // The menu drawer only exists below 1025px; don't leave it open (and the
    // page scroll-locked) when the window grows past that.
    var wide = window.matchMedia('(min-width: 1025px)');
    wide.addEventListener('change', function () {
      if (wide.matches && openDrawer && openDrawer.id === 'menu-drawer') closeDrawer(false);
    });

    // Drawer cards: the "+" disc expands that card's link list.
    document.querySelectorAll('.mb-card__toggle').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var open = btn.getAttribute('aria-expanded') !== 'true';
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        document.getElementById(btn.getAttribute('aria-controls')).hidden = !open;
      });
    });
  }

  // --- Home hero carousel ------------------------------------------------
  var hero = document.getElementById('hero');
  if (hero) {
    // The header is transparent while the whole hero is on screen, and turns
    // solid as soon as the hero's top edge scrolls under it.
    var siteHeader = document.querySelector('.site-header');
    var headerTick = false;
    var syncHeader = function () {
      headerTick = false;
      siteHeader.classList.toggle('is-solid', hero.getBoundingClientRect().top < 0);
    };
    window.addEventListener('scroll', function () {
      if (!headerTick) { headerTick = true; requestAnimationFrame(syncHeader); }
    }, { passive: true });
    window.addEventListener('resize', syncHeader);
    syncHeader();

    var slides = hero.querySelectorAll('.hs-slide');
    var controls = hero.querySelector('.hs-controls');
    if (controls && slides.length > 1) {
      var dots = hero.querySelectorAll('.hs-dot');
      var pauseBtn = hero.querySelector('.hs-pause');
      var INTERVAL = 6000;
      var current = 0;
      var timer = null;
      var playing = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      // Photos sit in data-src until their slide is (nearly) up.
      var prime = function (i) {
        var img = slides[i] && slides[i].querySelector('img[data-src]');
        if (img) { img.src = img.getAttribute('data-src'); img.removeAttribute('data-src'); }
      };

      var schedule = function () {
        clearTimeout(timer);
        // Hold still while someone is keyboard-focused inside the hero.
        if (!playing || document.hidden || hero.querySelector(':focus-visible')) return;
        timer = setTimeout(function () { go(current + 1); }, INTERVAL);
      };

      var go = function (i) {
        i = (i + slides.length) % slides.length;
        if (i !== current) {
          var prev = slides[current];
          prev.classList.remove('is-active');
          prev.setAttribute('aria-hidden', 'true');
          prev.inert = true;
          dots[current].removeAttribute('aria-current');
          current = i;
          prime(i);
          slides[i].classList.add('is-active');
          slides[i].removeAttribute('aria-hidden');
          slides[i].inert = false;
          dots[i].setAttribute('aria-current', 'true');
          prime((i + 1) % slides.length);
        }
        schedule();
      };

      var setPlaying = function (on) {
        playing = on;
        pauseBtn.classList.toggle('is-paused', !on);
        pauseBtn.setAttribute('aria-label', on ? 'Pause slideshow' : 'Play slideshow');
        // Announce slide changes only when the user is driving them.
        hero.setAttribute('aria-live', on ? 'off' : 'polite');
        schedule();
      };

      controls.hidden = false;
      dots.forEach(function (dot, i) {
        dot.addEventListener('click', function () { go(i); });
      });
      hero.querySelectorAll('[data-hs-step]').forEach(function (btn) {
        btn.addEventListener('click', function () {
          go(current + parseInt(btn.getAttribute('data-hs-step'), 10));
        });
      });
      pauseBtn.addEventListener('click', function () { setPlaying(!playing); });

      hero.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowLeft') go(current - 1);
        else if (e.key === 'ArrowRight') go(current + 1);
      });
      hero.addEventListener('focusin', schedule);
      hero.addEventListener('focusout', function () { setTimeout(schedule, 0); });
      document.addEventListener('visibilitychange', schedule);

      // Horizontal swipe on touch screens (vertical drags still scroll).
      var startX = null, startY = 0;
      hero.addEventListener('pointerdown', function (e) {
        if (e.pointerType !== 'mouse') { startX = e.clientX; startY = e.clientY; }
      });
      hero.addEventListener('pointercancel', function () { startX = null; });
      hero.addEventListener('pointerup', function (e) {
        if (startX === null) return;
        var dx = e.clientX - startX, dy = e.clientY - startY;
        startX = null;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) go(current + (dx < 0 ? 1 : -1));
      });

      // Fetch the next photo once the page itself has finished loading.
      if (document.readyState === 'complete') prime(1);
      else window.addEventListener('load', function () { prime(1); });
      setPlaying(playing);
    }
  }

  // --- Shop-by-category carousel -----------------------------------------
  // The row scrolls natively (swipe / trackpad); the arrows page it by one
  // view and grey out at either end.
  var rail = document.getElementById('cat-rail');
  if (rail) {
    var railBtns = document.querySelectorAll('[data-cat-step]');
    var syncRail = function () {
      var max = rail.scrollWidth - rail.clientWidth;
      railBtns.forEach(function (btn) {
        btn.hidden = max <= 1;
        btn.disabled = btn.getAttribute('data-cat-step') === '-1'
          ? rail.scrollLeft <= 1 : rail.scrollLeft >= max - 1;
      });
    };
    railBtns.forEach(function (btn) {
      btn.addEventListener('click', function () {
        rail.scrollBy({ left: parseInt(btn.getAttribute('data-cat-step'), 10) * rail.clientWidth * 0.9 });
      });
    });
    rail.addEventListener('scroll', syncRail, { passive: true });
    window.addEventListener('resize', syncRail);
    syncRail();
  }

  // --- Android app prompt ----------------------------------------------
  // Rendered hidden and only revealed here, so a dismissal is honoured before
  // the card can ever paint. iPhones are skipped: an APK is useless to them.
  var promo = document.getElementById('app-promo');
  if (promo) {
    var STORE_KEY = 'floralfinesse:appPromoDismissed';
    var SNOOZE_MS = 14 * 24 * 60 * 60 * 1000;   // shown again after two weeks
    var ua = navigator.userAgent || '';
    var isApple = /iPhone|iPad|iPod/.test(ua) ||
      // iPadOS 13+ reports itself as a Mac; the touch points give it away.
      (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);

    // Private-mode Safari throws on storage access — an unreadable store just
    // means we show the card, never that we break the page.
    var read = function () {
      try { return window.localStorage.getItem(STORE_KEY); } catch (e) { return null; }
    };
    var write = function (v) {
      try { window.localStorage.setItem(STORE_KEY, v); } catch (e) { /* ignore */ }
    };

    var dismissedAt = parseInt(read(), 10);
    var snoozed = dismissedAt && (Date.now() - dismissedAt) < SNOOZE_MS;

    if (!isApple && !snoozed) {
      // Let the page settle first — an offer that lands on top of content the
      // reader has not seen yet reads as an ad.
      setTimeout(function () { promo.hidden = false; }, 1400);
    }

    var closePromo = function () {
      write(String(Date.now()));
      promo.classList.add('is-leaving');
      setTimeout(function () { promo.hidden = true; promo.classList.remove('is-leaving'); }, 220);
    };
    document.getElementById('app-promo-close').addEventListener('click', closePromo);
    // Downloading is consent enough — don't nag afterwards.
    promo.querySelector('.app-promo-cta').addEventListener('click', function () {
      setTimeout(closePromo, 600);
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && !promo.hidden) closePromo();
    });
  }

  // --- Shop filters: collapsed on phones, always open on desktop ---------
  var filters = document.getElementById('filters');
  if (filters && filters.tagName === 'DETAILS') {
    var desktop = window.matchMedia('(min-width: 901px)');
    var syncFilters = function () { filters.open = desktop.matches; };
    desktop.addEventListener('change', syncFilters);
    syncFilters();
  }

  // --- Quantity steppers (+/-) -----------------------------------------
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-step]');
    if (!btn) return;
    var wrap = btn.closest('.qty');
    if (!wrap) return;
    var input = wrap.querySelector('input');
    var val = parseInt(input.value, 10) || 1;
    val += parseInt(btn.getAttribute('data-step'), 10);
    if (val < 1) val = 1;
    input.value = val;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  });

  // --- Product detail: image gallery ------------------------------------
  // Thumbnails swap the main photo; arrows, arrow keys and a swipe step
  // through every shot. Picking a colour jumps to that colour's first photo.
  var gallery = document.getElementById('gallery');
  var thumbs = gallery ? gallery.querySelectorAll('.gallery-thumb') : [];
  if (thumbs.length > 1) {
    var mainImg = document.getElementById('gallery-main-img');
    var indexEl = document.getElementById('gallery-index');
    var shown = 0;

    var show = function (i) {
      i = (i + thumbs.length) % thumbs.length;
      var t = thumbs[i];
      thumbs[shown].classList.remove('is-active');
      thumbs[shown].removeAttribute('aria-current');
      t.classList.add('is-active');
      t.setAttribute('aria-current', 'true');
      mainImg.src = t.getAttribute('data-full');
      mainImg.alt = t.getAttribute('data-alt');
      if (indexEl) indexEl.textContent = i + 1;
      // Keep the active thumbnail in view without scrolling the page.
      var rail = t.parentNode;
      if (rail.scrollHeight > rail.clientHeight) {
        rail.scrollTop = t.offsetTop - rail.offsetTop - (rail.clientHeight - t.offsetHeight) / 2;
      }
      if (rail.scrollWidth > rail.clientWidth) {
        rail.scrollLeft = t.offsetLeft - rail.offsetLeft - (rail.clientWidth - t.offsetWidth) / 2;
      }
      shown = i;
    };

    gallery.classList.add('is-live');
    thumbs.forEach(function (t, i) {
      t.addEventListener('click', function (e) { e.preventDefault(); show(i); });
    });
    gallery.querySelectorAll('[data-gallery-step]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        show(shown + parseInt(btn.getAttribute('data-gallery-step'), 10));
      });
    });
    gallery.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowLeft') show(shown - 1);
      else if (e.key === 'ArrowRight') show(shown + 1);
    });

    var galleryMain = document.getElementById('gallery-main');
    var gx = null, gy = 0;
    galleryMain.addEventListener('pointerdown', function (e) {
      if (e.pointerType !== 'mouse') { gx = e.clientX; gy = e.clientY; }
    });
    galleryMain.addEventListener('pointercancel', function () { gx = null; });
    galleryMain.addEventListener('pointerup', function (e) {
      if (gx === null) return;
      var dx = e.clientX - gx, dy = e.clientY - gy;
      gx = null;
      if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) show(shown + (dx < 0 ? 1 : -1));
    });

    var addForm = document.getElementById('add-form');
    if (addForm) {
      addForm.addEventListener('change', function (e) {
        if (e.target.name !== 'variant_id') return;
        for (var i = 0; i < thumbs.length; i++) {
          if (thumbs[i].getAttribute('data-variant') === e.target.value) { show(i); break; }
        }
      });
    }
  }

  // --- Product detail: live price preview -------------------------------
  var priceEl = document.getElementById('live-price');
  var dataEl = document.getElementById('price-data');
  if (priceEl && dataEl) {
    var data = JSON.parse(dataEl.textContent);
    var form = document.getElementById('add-form');

    function recompute() {
      var unit = parseFloat(data.final);
      var variant = form.querySelector('input[name="variant_id"]:checked');
      if (variant && data.variantDeltas[variant.value]) {
        unit += parseFloat(data.variantDeltas[variant.value]);
      }
      var meterSel = form.querySelector('[name="additional_meters"]');
      if (data.soldByMeters && meterSel) {
        unit += parseFloat(meterSel.value || '0') * parseFloat(data.extraPerMeter);
      }
      var qty = parseInt((form.querySelector('[name="quantity"]') || {}).value, 10) || 1;
      priceEl.textContent = rs(unit * qty);

      if (variant) {
        var label = document.getElementById('chosen-color');
        if (label) label.textContent = variant.getAttribute('data-name');
      }
    }

    form.addEventListener('change', recompute);
    form.addEventListener('input', recompute);
    recompute();
  }

  // --- Checkout: live shipping + total by province ----------------------
  var shipEl = document.getElementById('ship-amount');
  var totalEl = document.getElementById('grand-total');
  var ratesEl = document.getElementById('shipping-rates');
  var ckDataEl = document.getElementById('checkout-data');
  var provinceSel = document.getElementById('id_province');
  if (shipEl && totalEl && ratesEl && ckDataEl && provinceSel) {
    var rates = JSON.parse(ratesEl.textContent);
    var ck = JSON.parse(ckDataEl.textContent);
    var subtotal = parseFloat(ck.subtotal);
    var threshold = parseFloat(ck.freeThreshold || '0');
    var defaultFee = parseFloat(ck.defaultFee || '0');

    function updateShipping() {
      var p = provinceSel.value;
      if (!p) { shipEl.textContent = 'Select province'; totalEl.textContent = rs(subtotal); return; }
      var fee = (threshold > 0 && subtotal >= threshold)
        ? 0
        : (p in rates ? parseFloat(rates[p]) : defaultFee);
      shipEl.textContent = fee === 0 ? 'Free' : rs(fee);
      totalEl.textContent = rs(subtotal + fee);
    }
    provinceSel.addEventListener('change', updateShipping);
    updateShipping();
  }
})();
