/* ===========================================================================
   DANA — upload page behavior (app_media, v1.14)
   - G1 «پشت و رو گواهینامه و کارت ماشین»: bulk uploads + a **repeatable**
     confirm button (no timer)
   - G2 «شماره شاسی و پلاک‌ها» / G3 «اطراف ماشین»: bulk uploads + ONE final
     confirm button which runs the timing validation server-side
   - the same three groups for «مقصر» and for every زیان‌دیده (added with
     «اضافه کردن زیان دیده»; each has its own folder «شماره پلاک»)
   - every photo is stored right away, named after its field
     (car_card_front.jpg, chassis_number.jpg, …) — no GPS any more
   =========================================================================== */
(function () {
  'use strict';
  window.DANA = window.DANA || {};

  DANA.initUploadPage = function () {
    DANA.wireUploadArea(document);

    var csrf = DANA.csrf();

    /* ---- «اضافه کردن زیان دیده» — ONE button (v1.15): the bottom trigger ---- */
    var addBox = document.getElementById('victim-add-box');
    var form = document.getElementById('victim-form');
    var addBtn = document.getElementById('add-victim-btn');
    var vfPlate = document.getElementById('vf-plate');

    function clearVictimForm() {
      ['vf_first_name', 'vf_last_name', 'vf_national_code'].forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.value = '';
      });
      if (DANA.clearPlate && vfPlate) DANA.clearPlate(vfPlate);
    }
    function closeVictimForm() {
      if (form) form.classList.add('hidden');
      if (addBtn) addBtn.classList.remove('hidden');
      clearVictimForm();
    }
    function openVictimForm() {
      if (!form) return;
      form.classList.remove('hidden');
      // only one add button at a time — the trigger hides while the form is open
      if (addBtn) addBtn.classList.add('hidden');
      var first = document.getElementById('vf_first_name');
      if (first) first.focus();
      try { (addBox || form).scrollIntoView({ behavior: 'smooth', block: 'nearest' }); } catch (e) { }
    }
    document.addEventListener('click', function (e) {
      var trigger = e.target.closest ? e.target.closest('.victim-add-trigger') : null;
      if (trigger) { e.preventDefault(); openVictimForm(); }
    });

    var cancelBtn = document.getElementById('victim-cancel-btn');
    if (cancelBtn && form) {
      cancelBtn.addEventListener('click', function () { closeVictimForm(); });
    }

    /* «کد ملی» takes digits only — Persian digits are converted as you type */
    var ncInput = document.getElementById('vf_national_code');
    if (ncInput) {
      ncInput.addEventListener('input', function () {
        var cleaned = DANA.toEn(ncInput.value).replace(/\D/g, '').slice(0, 10);
        if (cleaned !== ncInput.value) ncInput.value = cleaned;
      });
    }

    var saveBtn = document.getElementById('victim-save-btn');
    if (saveBtn) {
      saveBtn.addEventListener('click', function () {
        var composed = DANA.composePlate ? DANA.composePlate(vfPlate) : null;
        if (!composed) {
          DANA.toast('«شماره پلاک» زیان‌دیده را کامل وارد کنید (۲ رقم، حرف، ۳ رقم).', true);
          return;
        }
        var ncError = DANA.nationalCodeError
          ? DANA.nationalCodeError((document.getElementById('vf_national_code') || {}).value)
          : '';
        if (ncError) { DANA.toast(ncError, true, 5000); return; }
        saveBtn.disabled = true;
        fetch('/victim/add/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrf,
            'Content-Type': 'application/json; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({
            first_name: ((document.getElementById('vf_first_name') || {}).value || '').trim(),
            last_name: ((document.getElementById('vf_last_name') || {}).value || '').trim(),
            national_code: DANA.toEn(((document.getElementById('vf_national_code') || {}).value || '')).trim(),
            // v1.21 — the «ایران ##» part travels (and is stored) on its own
            plate_number: composed.plate,
            plate_serial: composed.serial,
          }),
        })
          .then(function (r) { return r.json().then(function (d) { return [r.status, d]; }); })
          .then(function (pair) {
            saveBtn.disabled = false;
            var data = pair[1] || {};
            if (DANA.sessionExpired({ status: pair[0] }, data)) { DANA.gotoLogin(); return; }
            if (!data.ok) {
              DANA.toast(data.error || 'ثبت زیان‌دیده ناموفق بود', true);
              return;
            }
            var wrap = document.getElementById('victims-wrap');
            if (wrap && data.html) {
              var tmp = document.createElement('div');
              tmp.innerHTML = data.html.trim();
              while (tmp.firstChild) {
                var node = tmp.firstChild;
                wrap.appendChild(node);
                DANA.wireUploadArea(node);
              }
            }
            DANA.toast('زیان‌دیده «' + (data.victim && data.victim.plate || '') + '» اضافه شد');
            closeVictimForm();
          })
          .catch(function () {
            saveBtn.disabled = false;
            DANA.toast('خطا در ارتباط با سرور', true);
          });
      });
    }

    /* ---- «حذف زیان دیده» (removes the folder + images with it) ---- */
    document.addEventListener('click', function (e) {
      var btn = e.target.closest ? e.target.closest('.victim-remove-btn') : null;
      if (!btn) return;
      e.preventDefault();
      if (!confirm('زیان‌دیده «' + (btn.dataset.victimRemove || '') + '» با همهٔ تصاویرش حذف شود؟')) return;
      btn.disabled = true;
      var body = new URLSearchParams();
      body.set('id', btn.dataset.victimRemove || '');
      fetch('/victim/remove/', {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf, 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8' },
        body: body.toString(),
      })
        .then(function (r) { return r.json().then(function (d) { return [r, d]; }); })
        .then(function (pair) {
          if (DANA.sessionExpired(pair[0], pair[1])) { DANA.gotoLogin(); return; }
          var data = pair[1];
          if (!data || data.ok === false) {
            btn.disabled = false;
            DANA.toast((data && data.error) || 'حذف ناموفق بود', true);
            return;
          }
          var block = btn.closest('.victim-block');
          if (block) block.remove();
          DANA.toast('زیان‌دیده حذف شد');
        })
        .catch(function () {
          btn.disabled = false;
          DANA.toast('خطا در ارتباط با سرور', true);
        });
    });

    /* ---- finish (do NOT disable the button synchronously — that cancels
           the form submission in Chrome) ---- */
    var finishForm = document.getElementById('finish-form');
    var finishBtn = document.getElementById('finish-btn');
    if (finishForm && finishBtn) {
      finishForm.addEventListener('submit', function () {
        setTimeout(function () {
          finishBtn.disabled = true;
          finishBtn.textContent = 'در حال بررسی...';
        }, 0);
      });
    }
  };

  /* ---- v1.21 — HEIC/HEIF/DNG cannot be decoded by a browser: show a note
     instead of a broken image (the file itself is stored untouched). ---- */
  document.addEventListener('error', function (e) {
    var el = e.target;
    if (el && el.tagName === 'IMG' && el.closest) {
      var thumb = el.closest('.thumb');
      if (thumb) { thumb.classList.add('thumb-nopreview'); el.style.display = 'none'; }
    }
  }, true);

  /* =========================================================================
     One upload area (a field of a group) — bulk uploads, remove, drag&drop.
     Idempotent: every element is wired at most once, so freshly inserted
     زیان‌دیده blocks can be wired with the very same function.
     ========================================================================= */
  DANA.wireUploadArea = function (root) {
    root = root || document;
    var csrf = DANA.csrf();

    /* ---- accepted formats (v1.21) — the same list the server enforces ---- */
    var OK_EXT = /\.(jpe?g|png|heic|heif|dng)$/i;
    var OK_TYPE = ['image/jpeg', 'image/jpg', 'image/png', 'image/heic',
                   'image/heif', 'image/x-adobe-dng'];
    function accepted(file) {
      if (!file) return false;
      if (OK_EXT.test(file.name || '')) return true;
      return OK_TYPE.indexOf((file.type || '').toLowerCase()) >= 0;
    }

    /* ---- single-photo fields: buttons hide while the photo is there ---- */
    function syncSlot(area) {
      if (!area || area.dataset.single !== '1') return;
      var filled = area.querySelectorAll('.thumb').length > 0;
      area.classList.toggle('slot-has-image', filled);
    }
    DANA.syncSlot = syncSlot;

    function makeThumb(img, area) {
      var locked = area.dataset.locked === '1';
      var el = document.createElement('div');
      el.className = 'thumb';
      el.dataset.imgId = img.id;
      el.innerHTML =
        '<img src="' + img.url + '" alt="" data-lightbox="' + img.url + '">' +
        '<div class="thumb-meta"><div class="thumb-name"></div><div class="thumb-size"></div></div>' +
        (locked ? '' : '<button type="button" class="thumb-remove" title="حذف">✕</button>');
      el.querySelector('.thumb-name').textContent = img.name;
      el.querySelector('.thumb-size').textContent = DANA.formatSize(img.size);
      var rm = el.querySelector('.thumb-remove');
      if (rm) {
        rm.addEventListener('click', function () {
          if (!confirm('این تصویر حذف شود؟')) return;
          rm.disabled = true;
          fetch('/media/remove/' + img.id + '/', { method: 'POST', headers: { 'X-CSRFToken': csrf } })
            .then(function (r) { return r.json().then(function (d) { return [r, d]; }); })
            .then(function (pair) {
              if (DANA.sessionExpired(pair[0], pair[1])) { DANA.gotoLogin(); return; }
              var data = pair[1];
              if (data && data.ok === false) {
                rm.disabled = false;
                DANA.toast(data.error || 'حذف تصویر ناموفق بود', true);
                return;
              }
              el.remove();
              syncSlot(area);
            })
            .catch(function () {
              rm.disabled = false;
              DANA.toast('حذف تصویر ناموفق بود', true);
            });
        });
      }
      return el;
    }

    function uploadFile(file, area) {
      if (area.dataset.locked === '1') {
        DANA.toast('این بخش تأیید نهایی شده است.', true);
        return;
      }
      if (!accepted(file)) {
        DANA.toast('قالب فایل پذیرفته نیست — فقط JPG/JPEG، PNG، HEIC/HEIF و DNG (RAW) مجاز است.', true, 5000);
        return;
      }
      if (area.dataset.single === '1' && area.querySelector('.thumb')) {
        DANA.toast('برای این مورد قبلاً تصویر بارگذاری شده است؛ برای جایگزینی ابتدا آن را حذف کنید.', true, 5000);
        return;
      }
      var grid = area.querySelector('.thumb-grid');
      var ph = document.createElement('div');
      ph.className = 'thumb uploading';
      ph.innerHTML = '<div style="height:86px"></div><div class="thumb-spinner"><div class="spinner"></div></div>';
      grid.appendChild(ph);

      var fd = new FormData();
      fd.append('image', file);
      fd.append('section', area.dataset.section);
      if (area.dataset.party) fd.append('party', area.dataset.party);
      fetch('/media/upload/', { method: 'POST', headers: { 'X-CSRFToken': csrf }, body: fd })
        .then(function (res) { return res.json().then(function (d) { return [res, d]; }); })
        .then(function (pair) {
          ph.remove();
          if (DANA.sessionExpired(pair[0], pair[1])) { DANA.gotoLogin(); return; }
          var data = pair[1];
          if (!data.ok) { DANA.toast(data.error || 'آپلود ناموفق بود', true, 5000); return; }
          grid.appendChild(makeThumb(data.image, area));
          syncSlot(area);
        })
        .catch(function () {
          ph.remove();
          DANA.toast('خطا در آپلود تصویر', true);
        });
    }

    /* ---- the slot areas (each field = one area, bulk multi-image) ---- */
    root.querySelectorAll('.slot-area').forEach(function (area) {
      if (area.dataset.wired === '1') return;
      area.dataset.wired = '1';

      // server-rendered thumbs get their remove buttons here
      area.querySelectorAll('.thumb-remove[data-remove]').forEach(function (rm) {
        if (rm.dataset.wired === '1') return;
        rm.dataset.wired = '1';
        rm.addEventListener('click', function () {
          if (!confirm('این تصویر حذف شود؟')) return;
          rm.disabled = true;
          fetch('/media/remove/' + rm.dataset.remove + '/', { method: 'POST', headers: { 'X-CSRFToken': csrf } })
            .then(function (r) { return r.json().then(function (d) { return [r, d]; }); })
            .then(function (pair) {
              if (DANA.sessionExpired(pair[0], pair[1])) { DANA.gotoLogin(); return; }
              var data = pair[1];
              if (data && data.ok === false) {
                rm.disabled = false;
                DANA.toast(data.error || 'حذف تصویر ناموفق بود', true);
                return;
              }
              var thumb = rm.closest('.thumb');
              if (thumb) thumb.remove();
              syncSlot(rm.closest('.slot-area'));
            })
            .catch(function () {
              rm.disabled = false;
              DANA.toast('حذف تصویر ناموفق بود', true);
            });
        });
      });

      if (area.dataset.locked === '1') return;
      var cameraInput = area.querySelector('.file-camera');
      var galleryInput = area.querySelector('.file-gallery');
      if (!cameraInput || !galleryInput) return;
      area.querySelector('.act-camera').addEventListener('click', function () { cameraInput.click(); });
      area.querySelector('.act-gallery').addEventListener('click', function () { galleryInput.click(); });
      cameraInput.addEventListener('change', function () {
        Array.prototype.forEach.call(cameraInput.files, function (f) { uploadFile(f, area); });
        cameraInput.value = '';
      });
      galleryInput.addEventListener('change', function () {
        Array.prototype.forEach.call(galleryInput.files, function (f) { uploadFile(f, area); });
        galleryInput.value = '';
      });
      ['dragenter', 'dragover'].forEach(function (ev) {
        area.addEventListener(ev, function (e) { e.preventDefault(); area.classList.add('dragover'); });
      });
      ['dragleave', 'drop'].forEach(function (ev) {
        area.addEventListener(ev, function (e) { e.preventDefault(); area.classList.remove('dragover'); });
      });
      area.addEventListener('drop', function (e) {
        Array.prototype.forEach.call(e.dataTransfer.files, function (f) { uploadFile(f, area); });
      });
    });

    /* ---- the confirm buttons of the three groups ---- */
    root.querySelectorAll('.confirm-group-btn').forEach(function (btn) {
      if (btn.dataset.wired === '1') return;
      btn.dataset.wired = '1';
      btn.addEventListener('click', function () {
        var once = (btn.textContent || '').indexOf('فقط یک‌بار') >= 0;
        if (once && !confirm('تأیید نهایی فقط یک‌بار امکان‌پذیر است و پس از آن امکان افزودن یا حذف تصویر وجود ندارد. ادامه می‌دهید؟')) {
          return;
        }
        var original = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'در حال بررسی...';
        var body = new URLSearchParams();
        body.set('group', btn.dataset.confirmGroup || '');
        if (btn.dataset.party) body.set('party', btn.dataset.party);
        fetch('/media/confirm-group/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrf,
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
          },
          body: body.toString(),
        })
          .then(function (r) { return r.json().then(function (d) { return [r, d]; }); })
          .then(function (pair) {
            if (DANA.sessionExpired(pair[0], pair[1])) { DANA.gotoLogin(); return; }
            var data = pair[1];
            if (data.ok) {
              // v1.17 (owner): NO popup on success — a small toast for every
              // group (the popup belongs only to the timing-cancel error).
              DANA.toast('تأیید این بخش انجام شد');
              setTimeout(function () { location.reload(); }, 600);
              return;
            }
            btn.disabled = false;
            btn.textContent = original;
            if (data.car_group_reset) {
              // «زمان زیادی طول کشید!» — the ONLY popup left for uploads.
              DANA.popup({
                icon: '⏱',
                danger: true,
                title: 'زمان زیادی طول کشید!',
                sub: data.message || 'تصاویر این بخش حذف شدند؛ بقیهٔ تصاویر شما حفظ شده‌اند.',
                progress: 8000,
                button: { label: 'باشه' },
              });
              // v1.17 — stay on this page: remove ONLY the cancelled group's
              // thumbnails; the other images keep their place untouched.
              var grp = btn.dataset.confirmGroup || '';
              var sel = '.slot-area[data-group="' + grp + '"]';
              if (btn.dataset.party) sel += '[data-party="' + btn.dataset.party + '"]';
              document.querySelectorAll(sel).forEach(function (a) {
                a.querySelectorAll('.thumb').forEach(function (t) { t.remove(); });
                syncSlot(a);
              });
              return;
            }
            DANA.toast(data.already
              ? (data.error || 'این بخش قبلاً تأیید شده است.')
              : (data.error || 'تأیید این بخش انجام نشد.'), true);
          })
          .catch(function () {
            btn.disabled = false;
            btn.textContent = original;
            DANA.toast('خطا در ارتباط با سرور', true);
          });
      });
    });
  };
})();
