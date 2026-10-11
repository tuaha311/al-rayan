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
