/* ===========================================================================
   DANA — shared frontend utilities (vanilla JS, RTL, Persian digits)
   =========================================================================== */
(function () {
  'use strict';

  window.DANA = window.DANA || {};

  /* ---------- Persian digits ---------- */
  var FA = '۰۱۲۳۴۵۶۷۸۹';
  DANA.toFa = function (value) {
    return String(value).replace(/\d/g, function (d) { return FA[+d]; });
  };
  /* Persian / Arabic-Indic digits → ASCII (v1.21 — «کد ملی» validation) */
  DANA.toEn = function (value) {
    return String(value == null ? '' : value)
      .replace(/[\u06F0-\u06F9]/g, function (c) { return String(c.charCodeAt(0) - 0x06F0); })
      .replace(/[\u0660-\u0669]/g, function (c) { return String(c.charCodeAt(0) - 0x0660); });
  };
  /* «کد ملی» — exactly ten digits; '' means «not filled» (the field is optional) */
  DANA.nationalCodeError = function (value) {
    var code = DANA.toEn(value).replace(/[\s\-\u200c]/g, '');
    if (!code) return '';
    if (code.length !== 10 || !/^\d+$/.test(code)) {
      return 'کد ملی باید دقیقاً ۱۰ رقم و فقط عدد باشد.';
    }
    return '';
  };

  DANA.formatSize = function (bytes) {
    bytes = +bytes || 0;
    if (bytes < 1024) return DANA.toFa(bytes) + ' B';
    if (bytes < 1024 * 1024) return DANA.toFa((bytes / 1024).toFixed(1)) + ' KB';
    return DANA.toFa((bytes / 1024 / 1024).toFixed(1)) + ' MB';
  };

  DANA.csrf = function () {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : (document.cookie.match(/csrftoken=([^;]+)/) || [])[1] || '';
  };

  /* ---------- Session expiry on background requests (v1.21) ---------- */
  /* An expired session answers HTTP 401 + JSON instead of an HTML redirect, so
     every fetch() below can tell «the session is over» from «the server is
     broken» and walk the user back to the login page. */
  DANA.sessionExpired = function (response, data) {
    return (response && response.status === 401) || !!(data && data.session_expired);
  };
  DANA.gotoLogin = function () {
    window.location.href = '/?timeout=1';
  };

  DANA.debounce = function (fn, wait) {
    var t;
    return function () {
      var args = arguments, ctx = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, wait);
    };
  };

  /* ---------- Toast ---------- */
  DANA.toast = function (msg, danger, ms) {
    var old = document.querySelector('.toast');
    if (old) old.remove();
    var el = document.createElement('div');
    el.className = 'toast' + (danger ? ' danger' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, ms || 3200);
  };

  /* ---------- Popup (auto-dismiss or with button) ---------- */
  DANA.popup = function (opts) {
    // opts: {icon, title, sub, progress(ms), danger, button:{label, href}}
    var overlay = document.createElement('div');
    overlay.className = 'popup-overlay';
    var box = document.createElement('div');
    box.className = 'popup-box' + (opts.danger ? ' danger' : '');
    box.innerHTML =
      (opts.icon ? '<div class="popup-icon">' + opts.icon + '</div>' : '') +
      '<p class="popup-title"></p>' +
      (opts.sub ? '<p class="popup-sub"></p>' : '');
    box.querySelector('.popup-title').textContent = opts.title || '';
    if (opts.sub) box.querySelector('.popup-sub').textContent = opts.sub;
    if (opts.progress) {
      var bar = document.createElement('div');
      bar.className = 'popup-bar';
      bar.innerHTML = '<div class="popup-progress"></div>';
      box.appendChild(bar);
    }
    var hide = function () {
      overlay.style.opacity = '0';
      setTimeout(function () { overlay.remove(); }, 320);
    };
    if (opts.button) {
      var a = document.createElement('a');
      a.className = 'btn btn-primary';
      a.href = opts.button.href || '#';
      a.textContent = opts.button.label || 'باشه';
      // v1.17 — without an explicit href the button just closes the popup;
      // it must not navigate (a '#' history entry made the browser Back
      // button jump to the previous wizard step).
      a.addEventListener('click', function (ev) {
        if (!opts.button.href) { ev.preventDefault(); hide(); }
      });
      box.appendChild(a);
    }
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    if (opts.progress) setTimeout(hide, opts.progress);
    if (opts.dismissible) overlay.addEventListener('click', function (e) { if (e.target === overlay) hide(); });
    return hide;
  };

  /* Explicit, viewport-centered confirmation; Escape always cancels. */
  DANA.confirmUpload = function (message) {
    return new Promise(function (resolve) {
      var previous = document.activeElement;
      var dialog = document.createElement('dialog');
      dialog.className = 'popup-box upload-confirm-dialog';
      dialog.setAttribute('aria-labelledby', 'upload-confirm-title');
      dialog.setAttribute('aria-describedby', 'upload-confirm-message');
      dialog.innerHTML = '<h2 class="popup-title" id="upload-confirm-title">تأیید نهایی</h2>' +
        '<p class="popup-sub" id="upload-confirm-message"></p>' +
        '<form method="dialog" class="upload-confirm-actions">' +
        '<button class="btn btn-secondary" value="cancel" autofocus>انصراف</button>' +
        '<button class="btn btn-primary" value="confirm">تأیید و ادامه</button></form>';
      dialog.querySelector('.popup-sub').textContent = message;
      dialog.addEventListener('close', function () {
        var accepted = dialog.returnValue === 'confirm';
        dialog.remove();
        if (previous && previous.isConnected) previous.focus();
        resolve(accepted);
      }, { once: true });
      document.body.appendChild(dialog);
      dialog.showModal();
    });
  };

  /* ---------- Lightbox ---------- */
  (function () {
    function openLightbox(src) {
      if (!src || document.querySelector('.lightbox')) return;
      var lb = document.createElement('div');
      lb.className = 'lightbox';
      lb.innerHTML = '<button class="lb-close" type="button" aria-label="بستن">بستن</button>';
      var msg = document.createElement('div');
      msg.className = 'lb-error';
      msg.textContent = 'نمایش تصویر ممکن نشد';
      var img = document.createElement('img');
      img.alt = '';
      img.onload = function () { img.classList.add('lb-ready'); };
      img.onerror = function () { msg.style.display = 'block'; };
      img.src = src;
      lb.appendChild(img);
      lb.appendChild(msg);
      var close = function () {
        if (lb.parentNode) lb.parentNode.removeChild(lb);
        document.removeEventListener('keydown', onKey);
      };
      var onKey = function (e) { if (e.key === 'Escape') close(); };
      lb.addEventListener('click', close);
      document.body.appendChild(lb);
      document.addEventListener('keydown', onKey);
    }

    function ownerOf(el) {
      for (var n = el; n && n.nodeType === 1; n = n.parentNode) {
        if (n.getAttribute && n.getAttribute('data-lightbox')) return n;
      }
      return null;
    }

    function sourceOf(node) {
      return node.getAttribute('data-lightbox') || node.src || node.href || '';
    }

    function wire(node) {
      node.addEventListener('click', function (ev) {
        ev.preventDefault();
        ev.stopPropagation();
        openLightbox(sourceOf(node));
      });
    }

    document.addEventListener('click', function (e) {
      var t = ownerOf(e.target);
      if (t) { e.preventDefault(); openLightbox(sourceOf(t)); }
    });

    function wireAll() {
      var list = document.querySelectorAll('[data-lightbox]');
      for (var i = 0; i < list.length; i++) wire(list[i]);
    }
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', wireAll);
    } else {
      wireAll();
    }

    DANA.openLightbox = openLightbox;
  })();

  /* ---------- Searchable combobox ---------- */
  // Markup:
  //   <div class="cb" data-url="/records/search/?insurance=body&field=file_code&today=1" data-min="1">
  //     <input type="text" class="cb-input" ...>
  //   </div>
  DANA.initComboboxes = function (root) {
    (root || document).querySelectorAll('.cb').forEach(function (box) {
      if (box.dataset.cbInit) return;
      box.dataset.cbInit = '1';
      var input = box.querySelector('.cb-input');
      if (!input) return;
      var url = box.dataset.url || '';
      var minChars = parseInt(box.dataset.min || '1', 10);
      var list = null;
      var items = [];
      var hi = -1;

      function hideList() {
        if (list) { list.remove(); list = null; }
        items = []; hi = -1;
        box.classList.remove('cb-open');
        input.removeAttribute('aria-expanded');
      }
      function render(data) {
        hideList();
        // a late answer must not pop a list open after the field lost focus
        if (document.activeElement !== input) return;
        var q = input.value.trim();
        var note = data.note || '';
        if (!data.results || data.results.length === 0) {
          if (q.length >= minChars || note) {
            list = document.createElement('div');
            list.className = 'cb-list';
            list.innerHTML = (note ? '<div class="cb-note"></div>' : '') +
              (data.results && data.results.length === 0 && q.length >= minChars
                ? '<div class="cb-empty">موردی یافت نشد — مقدار را کامل وارد کنید</div>' : '');
            if (note) list.querySelector('.cb-note').textContent = note;
            box.appendChild(list);
            box.classList.add('cb-open');
          }
          return;
        }
        list = document.createElement('div');
        list.className = 'cb-list';
        items = data.results;
        if (note) {                       // «امروز پرونده‌ای ثبت نشده — آخرین پرونده‌ها»
          var noteEl = document.createElement('div');
          noteEl.className = 'cb-note';
          noteEl.textContent = note;
          list.appendChild(noteEl);
        }
        items.forEach(function (r, i) {
          var el = document.createElement('div');
          el.className = 'cb-item';
          el.setAttribute('role', 'option');
          var valueEl = document.createElement('span');
          valueEl.className = 'cb-value mono';
          valueEl.textContent = r.value;
          var labelEl = document.createElement('span');
          labelEl.className = 'cb-label';
          labelEl.textContent = r.label || '';
          el.appendChild(valueEl);
          if (r.label) el.appendChild(labelEl);
          el.addEventListener('mousedown', function (ev) { ev.preventDefault(); pick(i); });
          list.appendChild(el);
        });
        box.appendChild(list);
        box.classList.add('cb-open');       // paints above sibling tabs/cards
        input.setAttribute('aria-expanded', 'true');
      }
      function pick(i) {
        var r = items[i];
        if (!r) return;
        input.value = r.value;
        input.dispatchEvent(new Event('change', { bubbles: true }));
        hideList();
        input.blur();
      }
      var field = box.dataset.field || '';
      var today = box.dataset.today || '0';
      function currentInsurance() {
        var insEl = document.querySelector('input[name="insurance_type"]:checked');
        if (insEl) return insEl.value;
        var pageEl = box.closest('[data-insurance]') ||
          document.querySelector('[data-insurance]');
        return (pageEl && pageEl.dataset.insurance) || box.dataset.insurance || 'body';
      }
      function buildUrl(q) {
        if (!field) {
          var sep = url.indexOf('?') >= 0 ? '&' : '?';
          return url + sep + 'q=' + encodeURIComponent(q);
        }
        var params = [
          'insurance=' + currentInsurance(),
          'field=' + field,
          'today=' + today,
          'q=' + encodeURIComponent(q),
        ];
        return url + (url.indexOf('?') >= 0 ? '&' : '?') + params.join('&');
      }
      var doSearch = DANA.debounce(function () {
        var q = input.value.trim();
        if (q.length < minChars) { hideList(); return; }
        fetch(buildUrl(q), { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
          .then(function (res) { return res.json(); })
          .then(render)
          .catch(hideList);
      }, 250);

      input.addEventListener('input', doSearch);
      input.addEventListener('focus', doSearch);
      // leaving the field closes its list, so an open dropdown can never sit on
      // top of another control and swallow the click (v1.10)
      input.addEventListener('blur', function () {
        setTimeout(function () {
          if (list && !box.contains(document.activeElement)) hideList();
        }, 160);
      });
      input.addEventListener('keydown', function (e) {
        if (!list) return;
        if (e.key === 'ArrowDown') { e.preventDefault(); hi = Math.min(hi + 1, items.length - 1); paint(); }
        else if (e.key === 'ArrowUp') { e.preventDefault(); hi = Math.max(hi - 1, 0); paint(); }
        else if (e.key === 'Enter' && hi >= 0) { e.preventDefault(); pick(hi); }
        else if (e.key === 'Escape') { hideList(); }
      });
      function paint() {
        list.querySelectorAll('.cb-item').forEach(function (el, i) {
          el.classList.toggle('hi', i === hi);
          if (i === hi) el.scrollIntoView({ block: 'nearest' });
        });
      }
      document.addEventListener('click', function (e) { if (!box.contains(e.target)) hideList(); });
    });
  };

  /* ---------- Plate component (v1.15 — every widget on the page) ---------- */
  DANA.initPlate = function (root) {
    (root || document).querySelectorAll('.plate').forEach(function (plate) {
      if (plate.dataset.plateInit) return;
      plate.dataset.plateInit = '1';
      var digits = Array.prototype.slice.call(plate.querySelectorAll('.plate-digit'));
      var letter = plate.querySelector('.plate-letter');
      function liveList() {
        return Array.prototype.slice.call(plate.querySelectorAll('.plate-digit')).filter(function (d) { return !d.disabled; });
      }
      digits.forEach(function (inp) {
        inp.addEventListener('input', function (e) {
          var v = e.target.value;
          if (v.length > 1) v = v.slice(-1);
          if (v && !/[\d۰-۹٠-٩]/.test(v)) v = '';
          e.target.value = v;
          if (v) {
            var list = liveList();
            var next = list[list.indexOf(inp) + 1];
            if (next) { next.focus(); return; }
            if (letter && !letter.disabled && inp === list[1]) letter.focus();
          }
        });
        inp.addEventListener('keydown', function (e) {
          if (e.key === 'Backspace' && !inp.value) {
            var list = liveList();
            var prev = list[list.indexOf(inp) - 1];
            if (prev) { e.preventDefault(); prev.focus(); prev.value = ''; }
          }
        });
        inp.addEventListener('paste', function (e) {
          e.preventDefault();
          var paste = (e.clipboardData || window.clipboardData).getData('text');
          var chars = paste.replace(/[^0-9۰-۹٠-٩]/g, '').split('');
          var list = liveList();
          var start = list.indexOf(inp);
          chars.forEach(function (c, i) { if (list[start + i]) list[start + i].value = c; });
          var last = list[Math.min(start + chars.length, list.length - 1)];
          if (last) last.focus();
        });
      });
      if (letter) {
        letter.addEventListener('change', function () {
          var firstEmpty = liveList().filter(function (d) { return !d.value; })[0];
          if (firstEmpty) firstEmpty.focus();
        });
      }
    });
  };

  /* ---------- Plate component: compose the slots into a plate string ------- */
  /* «12ب345» + optional serial «21» → value «12ب345-21» (the same format the
     server's build_plate_value / plate_slots use). The digit slots are read in
     DOM order (d1 d2 · d3 d4 d5 · ir1 ir2) so every plate widget works.
     Returns null when the main 6 slots are incomplete. */
  DANA.composePlate = function (plate) {
    if (!plate) return null;
    function fa2en(v) {
      return (v || '').trim()
        .replace(/[۰-۹]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x06F0); })
        .replace(/[٠-٩]/g, function (c) { return String.fromCharCode(c.charCodeAt(0) - 0x0660); });
    }
    var slots = Array.prototype.slice.call(plate.querySelectorAll('.plate-digit')).map(function (i) {
      return fa2en(i.value);
    });
    var letter = (plate.querySelector('.plate-letter') || {}).value || '';
    var d1 = slots[0] || '', d2 = slots[1] || '', d3 = slots[2] || '', d4 = slots[3] || '', d5 = slots[4] || '';
    var ir1 = slots[5] || '', ir2 = slots[6] || '';
    if (!(d1 && d2 && letter && d3 && d4 && d5)) return null;
    var main = d1 + d2 + letter + d3 + d4 + d5;
    var serial = (ir1 + ir2).replace(/[^0-9]/g, '');
    return {
      plate: main,
      serial: serial,
      value: serial ? main + '-' + serial : main,
    };
  };

  DANA.clearPlate = function (plate) {
    if (!plate) return;
    plate.querySelectorAll('.plate-digit').forEach(function (i) { i.value = ''; });
    var letter = plate.querySelector('.plate-letter');
    if (letter) letter.value = '';
  };

  /* ---------- Development: the tiny footer box (v1.13) ---------- */
  /* =========================================================================
     The unlabeled box in the footer of the page right before the upload page.
     It changes a value that normally lives in `.env` (CAR_IMAGE_MAX_GAP_SECONDS)
     for the current session: type a number → the server stores the override;
     empty the box → back to the `.env` value. Development only.
     ========================================================================= */
  DANA.initDevGap = function () {
    var input = document.getElementById('dev-gap-input');
    if (!input) return;
    var url = input.dataset.url;
    var key = input.dataset.key;
    var configured = input.value;

    function flash(cls) {
      input.classList.add(cls);
      setTimeout(function () { input.classList.remove(cls); }, 1200);
    }

    function save() {
      var body = new URLSearchParams();
      body.set('key', key);
      body.set('value', input.value.trim());
      fetch(url, {
        method: 'POST',
        headers: {
          'X-CSRFToken': DANA.csrf(),
          'X-Requested-With': 'XMLHttpRequest',
          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        },
        body: body.toString(),
      }).then(function (r) { return r.json().then(function (d) { return [r.status, d]; }); })
        .then(function (pair) {
          var status = pair[0], data = pair[1];
          if (!data || data.ok !== true) {
            DANA.toast((data && data.error) || 'ذخیره نشد', true);
            input.value = configured;
            flash('dev-error');
            return;
          }
          input.dataset.overridden = data.overridden ? '1' : '';
          configured = data.value;
          input.value = data.value;      // emptied → shows the .env value again
          flash('dev-saved');
        })
        .catch(function () { DANA.toast('ارتباط برقرار نشد', true); });
    }

    input.addEventListener('change', save);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); input.blur(); }
    });
  };

  /* ---------- Session countdown (v1.12) ---------- */
  /* =========================================================================
     Session timeout UI («مهلت نشست»)
     The server is authoritative (SessionTimeoutMiddleware); this only shows the
     remaining time, warns before the end, and pushes the deadline away when the
     user presses «ادامهٔ کار». The payload comes from base.html as
     window.DANA_TIMEOUT.
     ========================================================================= */
  DANA.initTimeout = function (payload) {
    var cfg = payload || window.DANA_TIMEOUT || null;
    if (!cfg || !cfg.enabled) return;

    var warnAt = parseInt(cfg.warn, 10) || 15;
    var total = parseInt(cfg.total, 10) || 600;
    var overlay = null, countEl = null, timer = null, lastPing = 0;
    var lastActivity = Date.now();
    var closed = false;
    /* v1.21 — the countdown is derived from a **deadline timestamp**, not from
       a «-1 every tick» counter: a throttled or sleeping tab no longer drifts
       away from the server clock (that drift is what made the popup fire long
       after the session had really ended). */
    var deadline = Date.now() + (parseInt(cfg.remaining, 10) || 0) * 1000;
    var remaining = Math.round((deadline - Date.now()) / 1000);

    function setRemaining(seconds) {
      deadline = Date.now() + (parseInt(seconds, 10) || 0) * 1000;
      remaining = Math.round((deadline - Date.now()) / 1000);
    }

    function fmt(seconds) {
      seconds = Math.max(0, seconds);
      var m = Math.floor(seconds / 60), s = seconds % 60;
      return DANA.toFa(m) + ':' + DANA.toFa(('0' + s).slice(-2));
    }

    function build() {
      overlay = document.createElement('div');
      overlay.className = 'timeout-overlay';
      overlay.innerHTML =
        '<div class="timeout-box" role="alertdialog" aria-live="assertive">' +
        '  <p class="timeout-title">مهلت نشست در حال پایان است</p>' +
        '  <p class="timeout-text">بر اساس آخرین فعالیت شما، تا پایان خودکار نشست باقی مانده:</p>' +
        '  <p class="timeout-count">۰:۰۰</p>' +
        '  <div class="timeout-actions">' +
        '    <button type="button" class="btn btn-primary timeout-continue">ادامهٔ کار</button>' +
        '    <a class="btn btn-secondary timeout-exit" href="' + (cfg.logoutUrl || '/logout/') + '">خروج</a>' +
        '  </div>' +
        '  <p class="timeout-hint">اگر کاری انجام نشود، به‌صورت خودکار از سامانه خارج می‌شوید.</p>' +
        '</div>';
      document.body.appendChild(overlay);
      countEl = overlay.querySelector('.timeout-count');
      overlay.querySelector('.timeout-continue').addEventListener('click', ping);
    }

    function show() { if (overlay) overlay.classList.add('visible'); }
    function hide() { if (overlay) overlay.classList.remove('visible'); }

    function paint() {
      if (countEl) countEl.textContent = fmt(remaining);
      if (remaining <= warnAt) show();
    }

    function ping() {
      var now = Date.now();
      if (now - lastPing < 1500) return;          // keep double clicks cheap
      lastPing = now;
      fetch(cfg.pingUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) {
          if (r.status === 401) { leave(0); return null; }   // session already closed
          return r.json();
        })
        .then(function (data) {
          if (!data) return;
          if (data.ok === false) { leave(0); return; }
          setRemaining(data.remaining);
          hide();
          paint();
        })
        .catch(function () { /* offline: the countdown keeps running */ });
    }

    /* Coming back from a hidden tab / a suspended laptop: the local clock says
       nothing trustworthy, so ask the server how much time is really left —
       and only log out when the server says the session is gone. */
    function resync() {
      if (closed) return;
      lastPing = 0;
      fetch(cfg.pingUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) {
          if (r.status === 401) { leave(0); return null; }
          return r.json();
        })
        .then(function (data) {
          if (!data) return;
          if (data.ok === false) { leave(0); return; }
          setRemaining(data.remaining);
          paint();
        })
        .catch(function () { /* offline: the local countdown keeps running */ });
    }

    function leave(grace) {
      if (closed) return;
      closed = true;
      if (timer) clearInterval(timer);
      // a couple of seconds of grace so the server clock has certainly run out
      // too — otherwise the session could look still-alive on the next page
      var wait = typeof grace === 'number' ? grace : 2500;
      if (overlay) {
        overlay.querySelector('.timeout-title').textContent = 'در حال خروج از سامانه…';
        overlay.querySelector('.timeout-text').textContent =
          'به‌دلیل پایان مهلت نشست، به صفحهٔ ورود بازمی‌گردید.';
        overlay.querySelector('.timeout-actions').style.display = 'none';
        overlay.querySelector('.timeout-hint').style.display = 'none';
        show();
      }
      window.setTimeout(function () {
        window.location.href = cfg.timeoutUrl || '/?timeout=1';
      }, wait);
    }

    function activity() {
      var now = Date.now();
      if (now - lastActivity < 5000) return;      // throttle
      lastActivity = now;
      // only refresh when the deadline is getting close: a normal session then
      // costs one request every few minutes instead of one per click
      if (remaining <= Math.min(total, warnAt * 3)) ping();
    }

    build();
    paint();
    timer = setInterval(function () {
      /* a hidden tab is not counted down: the user is not here, and the server
         clock is the authority anyway (resync() settles it on their return). */
      if (document.hidden) return;
      remaining = Math.round((deadline - Date.now()) / 1000);
      paint();
      if (remaining <= 0) leave();
    }, 1000);
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) resync();
    });
    window.addEventListener('focus', resync);
    ['mousemove', 'mousedown', 'keydown', 'touchstart', 'scroll'].forEach(function (ev) {
      document.addEventListener(ev, activity, { passive: true });
    });
  };

  /* ---------- Login form (v1.14 — no user-type cards; type = prefix) ---------- */
  DANA.initLogin = function () {
    var page = document.getElementById('login-page');
    if (!page) return;

    var usernameEl = document.getElementById('id_username');
    var passwordEl = document.getElementById('id_password');
    var passwordRow = document.getElementById('password-row');
    var noteEl = document.getElementById('auth-prefix-note');

    /* The user type comes from the first letter of the username:
       «p» → کارشناس · «د» (or the legacy «n»/«d») → نماینده. Nothing else is
       validated here — the server repeats the single prefix error. */
    function detectPrefix(typed) {
      if (!typed) return null;
      var first = typed.trim().toLowerCase().charAt(0);
      if (first === 'p') return { label: 'کارشناس' };
      if (first === 'د' || first === 'n' || first === 'd') return { label: 'نماینده' };
      return { label: '' };
    }

    var passwordHintDefault = 'اگر حساب شما رمز عبور ندارد (غیرفعال است)، این کادر را خالی بگذارید.';
    function resetPassword() {
      if (!passwordRow) return;
      passwordRow.classList.remove('hidden', 'password-off');
      var hint = document.getElementById('password-hint');
      if (hint) { hint.textContent = passwordHintDefault; hint.classList.remove('warn'); }
      var star = document.getElementById('password-required');
      if (star) star.classList.remove('hidden');
    }

    var checkTimer = null;
    function checkAccount() {
      if (!usernameEl) return;
      var typed = usernameEl.value.trim();
      if (!typed) { resetPassword(); return; }
      fetch('/login/check-user/?username=' + encodeURIComponent(typed),
            { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data || !data.valid) { resetPassword(); return; }
          var hint = document.getElementById('password-hint');
          if (!data.exists) {
            resetPassword();
            if (hint) { hint.textContent = 'حسابی با این نام کاربری یافت نشد.'; hint.classList.add('warn'); }
            return;
          }
          if (!data.needs_password) {
            // account without a password → the user signs in with the username alone
            if (passwordRow) passwordRow.classList.add('hidden');
            if (hint) { hint.textContent = 'این حساب رمز عبور ندارد؛ با زدن «ورود و ادامه» وارد می‌شوید.'; hint.classList.remove('warn'); }
          } else {
            resetPassword();
            if (hint) { hint.textContent = 'این حساب رمز عبور دارد؛ آن را وارد کنید.'; hint.classList.remove('warn'); }
            if (passwordEl && !passwordEl.value) passwordEl.focus();
          }
        })
        .catch(function () { /* offline: the server decides anyway */ });
    }

    if (usernameEl) {
      usernameEl.addEventListener('input', function () {
        if (!noteEl) return;
        var typed = usernameEl.value.trim();
        var d = detectPrefix(typed);
        noteEl.classList.remove('ok', 'warn');
        if (!typed) { noteEl.textContent = ''; return; }
        if (d && d.label) {
          noteEl.textContent = d.label;
          noteEl.classList.add('ok');
        } else {
          noteEl.textContent = 'نام کاربری باید با حرف «p» (کارشناس) یا «د» (نماینده) شروع شود.';
          noteEl.classList.add('warn');
        }
      });
      usernameEl.addEventListener('blur', checkAccount);
      ['keyup', 'change'].forEach(function (ev) {
        usernameEl.addEventListener(ev, function () {
          clearTimeout(checkTimer);
          checkTimer = setTimeout(checkAccount, 500);
        });
      });
      checkAccount();
    }

    /* ---- نوع بیمه cards -> live theme ---- */
    page.querySelectorAll('input[name="insurance_type"]').forEach(function (r) {
      r.addEventListener('change', function () {
        document.documentElement.dataset.theme =
          r.value === 'body' ? 'badene' : (r.value === 'third' ? 'satheth' : 'default');
      });
    });
  };

  /* ---------- Case finder (the old «اطلاعات» page — now on the upload page) ---------- */
  DANA.initCaseFinder = function () {
    var page = document.getElementById('upload-page') || document.getElementById('login-page');
    if (!page) return;
    var insurance = page.dataset.insurance || '';
    var form = document.getElementById('step3-form');
    if (!form) return;

    var panel = document.getElementById('record-panel');
    var panelTitle = document.getElementById('record-panel-title');
    var panelBody = document.getElementById('record-panel-body');

    /* «اطلاعات پرونده» panel — the small scrollable box (the only info box) */
    function showDetails(field, value) {
      if (!panel || !value) return;
      var qs = '/records/details/?insurance=' + encodeURIComponent(insurance) +
        '&field=' + encodeURIComponent(field) + '&value=' + encodeURIComponent(value);
      fetch(qs, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data.found) { panel.classList.add('hidden'); return; }
          panelTitle.textContent = data.title || '';
          panelBody.innerHTML = '';
          (data.details || []).forEach(function (row) {
            var div = document.createElement('div');
            div.className = 'info-row';
            var l = document.createElement('span'); l.className = 'info-label'; l.textContent = row.label;
            var v = document.createElement('span'); v.className = 'info-value'; v.textContent = row.value;
            div.appendChild(l); div.appendChild(v);
            panelBody.appendChild(div);
          });
          panel.classList.remove('hidden');
        })
        .catch(function () { /* ignore */ });
    }
    DANA.showDetails = showDetails;

    DANA.initComboboxes(page);
    form.querySelectorAll('.cb-input').forEach(function (input) {
      input.addEventListener('change', function () {
        var cb = input.closest('.cb');
        if (cb && cb.dataset.field) showDetails(cb.dataset.field, input.value.trim());
      });
    });

    /* ---- plate-changed branch (بدنه) ---- */
    var plateChk = page.querySelector('input[name="plate_changed"]');
    var plateWrap = page.querySelector('#plate-branch');
    if (plateChk && plateWrap) {
      var syncPlate = function () {
        plateWrap.classList.toggle('hidden', !plateChk.checked);
        plateWrap.querySelectorAll('.plate-digit, .plate-letter').forEach(function (el) {
          el.disabled = !plateChk.checked;
        });
      };
      plateChk.addEventListener('change', syncPlate);
      syncPlate();
    }
    DANA.initPlate(page);
  };
  /* ================================================================
     Browser back button = the app's own back button (v1.14).
     `window.DANA_BACK` (set by base.html) is the page's logical
     predecessor; we rewrite the current history entry so pressing
     «بازگشت» never pops the user out of the wizard.
     ================================================================ */
  (function wireBack() {
    var back = window.DANA_BACK || '';
    if (!back) return;
    try {
      history.replaceState({ danaBack: back }, '', location.href);
    } catch (e) { /* file:// or old browser — ignore */ }
    window.addEventListener('popstate', function () {
      location.replace(back);
    });
  })();

})();
