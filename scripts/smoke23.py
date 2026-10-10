"""smoke23.py — full pipeline smoke for the DANA app (v1.19).

Run (Windows-safe, no shell scripts):
    .venv/bin/python scripts/smoke23.py

Covers: login → نوع بیمه → resolve → sections/uploads → group confirms →
timing-cancel (stays on page, only the timed group is discarded) → victim →
finalize (watermark v1.19: four values + logos + fail-safe QR) → /wm-info/
page → static texts → only stamped files remain.

Kept in git (``scripts/``) so environment/snapshot wipes cannot lose it;
scratch artifacts still go to ``storage/tmp/`` (gitignored).
"""
import io
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dana.settings')

import django  # noqa: E402

django.setup()

from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from PIL import Image as PILImage  # noqa: E402

from app_media.constants import (MULTI_PHOTO_SECTIONS,  # noqa: E402
                                 SECTION_KEYS, SECTION_MIN)
from app_media.models import CaseImage  # noqa: E402
from app_media.services import storage, watermark as wm  # noqa: E402

PASS, FAIL = 0, 0
UPLOADED = []          # image ids created by THIS run (rows can die in E)
TMP = REPO / 'storage' / 'tmp'
TMP.mkdir(parents=True, exist_ok=True)


def check(label, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ok  {label}')
    else:
        FAIL += 1
        print(f'FAIL  {label}  {extra}')


def jpeg(color, size=(900, 700)):
    """A fresh JPEG the uploads accept."""
    img = PILImage.new('RGB', size, color)
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return SimpleUploadedFile(f'{color[0]}{color[1]}{color[2]}.jpg',
                              buf.getvalue(), 'image/jpeg')


def upload_sections(client, party, colors):
    """Upload SECTION_MIN photos for every section of one owner."""
    ids = []
    for section in SECTION_KEYS:
        n = SECTION_MIN.get(section, 1)
        for i in range(n):
            r = client.post('/media/upload/', {
                'section': section,
                'party': party,
                'image': jpeg(colors[i % len(colors)]),
            })
            check(f'upload {section or "?"} #{i + 1} (party={party or "owner"}) ok',
                  r.status_code == 200 and r.json().get('ok') is True,
                  f'status={r.status_code}')
            img_id = (r.json().get('image') or {}).get('id')
            ids.append(img_id)
            UPLOADED.append(img_id)
    return ids


def confirm_groups(client, party, prefix=''):
    for group in ('group_docs', 'group_plates', 'group_car'):
        r = client.post('/media/confirm-group/', {'group': group, 'party': party})
        check(f'{prefix}confirm {group} ok',
              r.status_code == 200 and r.json().get('ok') is True,
              f'status={r.status_code} body={r.content[:120]}')


# ---------------------------------------------------------------- tests ----
print('== A. pages & login ==')
anon = Client()
check('GET / ok', anon.get('/').status_code == 200)
check('GET /wm-info/ public (anonymous) ok', anon.get('/wm-info/').status_code == 200)

c = Client()
r = c.post('/login/', {'stage': '1', 'username': 'palireza', 'password': '123456'})
check('login stage 1 → 302', r.status_code == 302, f'{r.status_code}')
r = c.post('/login/', {'stage': '2', 'insurance_type': 'third'})
check('login stage 2 (نوع بیمه) → 302 upload', r.status_code == 302, f'{r.status_code}')
r = c.get('/step2-upload/')
check('upload page 200', r.status_code == 200)
# v1.21 — the brand logos come from ONE partial; both files must resolve on
# every page that shows them (an empty path would render src="/static/")
for _name, _html in (('login page', anon.get('/').content.decode()),
                     ('upload page', r.content.decode())):
    check(f'{_name}: both brand logos resolve',
          'dana-logo.png' in _html and 'hef.co.ir.png' in _html
          and 'src="/static/"' not in _html, _html[:0] or 'a logo path is empty')

print('== B. resolve ==')
r = c.post('/case/resolve/', {'file_code': '22241712'})
check('resolve 22241712 → upload page', r.status_code == 302, f'{r.status_code}')
body = c.get('/step2-upload/').content.decode()
check('upload page shows case code', '22241712' in body)

print('== C. static texts (user-editable in template) ==')
for text in ('پشت و رو گواهینامه و کارت ماشین',
             'تصاویر را پشت سر هم بگیرید',
             'حداقل ۴ تصویر'):
    check(f'upload page shows «{text[:24]}…»', text in body)
tpl = (REPO / 'templates' / 'main' / '_party_groups.html').read_text(encoding='utf-8')
for text in ('پشت و رو گواهینامه و کارت ماشین',
             'تصاویر را پشت سر هم بگیرید',
             'حداقل ۴ تصویر'):
    check(f'template holds «{text[:24]}…» statically', text in tpl)

print('== D. مقصر uploads & confirms ==')
owner_ids = upload_sections(c, '', [(200, 80, 80), (80, 200, 80), (80, 80, 200),
                                    (200, 200, 80)])
body = c.get('/step2-upload/').content.decode()
check('owner thumbs rendered', body.count('thumb') >= 8, f"count={body.count('thumb')}")
confirm_groups(c, '')
body = c.get('/step2-upload/').content.decode()
check('owner groups locked after confirm', body.count('data-locked="1"') >= 1)

print('== E. timing-cancel ==')
r = c.post('/victim/add/', data='{"plate_number": "12345678"}',
           content_type='application/json')
check('victim added', r.status_code == 200 and r.json().get('ok') is True,
      f'{r.status_code} {r.content[:100]}')
victim_id = str((r.json().get('victim') or {}).get('id'))
# victim: docs + plates first (they must survive the car timing violation)
for section in SECTION_KEYS:
    if section in MULTI_PHOTO_SECTIONS:
        continue
    for i in range(SECTION_MIN.get(section, 1)):
        r = c.post('/media/upload/', {'section': section, 'party': victim_id,
                                      'image': jpeg((120, 120, 60))})
        check(f'victim upload {section}', r.status_code == 200 and r.json().get('ok'))
        UPLOADED.append((r.json().get('image') or {}).get('id'))
for group in ('group_docs', 'group_plates'):
    r = c.post('/media/confirm-group/', {'group': group, 'party': victim_id})
    check(f'victim confirm {group}', r.json().get('ok') is True)
# car shots — then backdate so the gap rule trips
car_ids = []
for i in range(SECTION_MIN['car_shots']):
    r = c.post('/media/upload/', {'section': 'car_shots', 'party': victim_id,
                                  'image': jpeg((60, 60, 120))})
    car_ids.append((r.json().get('image') or {}).get('id'))
UPLOADED.extend(car_ids)
check('victim car_shots uploaded', len(car_ids) == SECTION_MIN['car_shots'])
# spread the shots 20 minutes apart (gap ≫ 10 s AND span ≫ 10 min → violation)
base = timezone.now() - timezone.timedelta(hours=2)
for k, cid in enumerate(car_ids):
    CaseImage.objects.filter(id=cid).update(
        uploaded_at=base + timezone.timedelta(minutes=20 * k))
r = c.post('/media/confirm-group/', {'group': 'group_car', 'party': victim_id})
j = r.json()
check('timing violation → car_group_reset', j.get('car_group_reset') is True, str(j)[:160])
check('reset message says «زمان زیادی طول کشید»', 'زمان زیادی طول کشید' in (j.get('message') or ''),
      str(j.get('message'))[:80])
check('timed group thumbs discarded', not CaseImage.objects.filter(id__in=car_ids).exists())
body = c.get('/step2-upload/').content.decode()
check('docs thumbs survive the car reset', body.count('thumb') >= 4)
check('page did not navigate away (upload page still served)',
      c.get('/step2-upload/').status_code == 200)

print('== F. victim re-shoot + confirm ==')
for i in range(SECTION_MIN['car_shots']):
    r = c.post('/media/upload/', {'section': 'car_shots', 'party': victim_id,
                                  'image': jpeg((90, 140, 200))})
    check(f'victim re-shoot car_shots #{i + 1}',
          r.status_code == 200 and r.json().get('ok') is True)
    UPLOADED.append((r.json().get('image') or {}).get('id'))
r = c.post('/media/confirm-group/', {'group': 'group_car', 'party': victim_id})
check('victim confirm group_car after re-shoot', r.json().get('ok') is True,
      r.content[:120].decode())
# v1.21 — EVERY group confirms exactly once, the docs group included
for _g, _who in (('group_car', victim_id), ('group_docs', victim_id),
                 ('group_plates', ''), ('group_docs', '')):
    r = c.post('/media/confirm-group/', {'group': _g, 'party': _who})
    check(f'second confirm of {_g} ({_who or "مقصر"}) refused',
          r.json().get('ok') is False and r.json().get('already') is True,
          r.content[:120].decode())
# … and the locked group no longer offers a confirm button
b = c.get('/step2-upload/').content.decode()
check('no confirm button left for a locked group',
      'data-confirm-group="group_docs"' not in b
      and 'data-confirm-group="group_plates"' not in b)
check('locked note carries the confirmation time',
      'تأیید نهایی این بخش انجام شده است' in b)

print('== G. finalize + watermark v1.19 ==')
rows = CaseImage.objects.filter(id__in=UPLOADED)
before = {storage.root() / img.image_path: (storage.root() / img.image_path).read_bytes()
          for img in rows}
seen_infos = []
orig_stamp = wm.simple_watermark_file


def spy_stamp(path, code, cfg=None, dest=None):
    seen_infos.append(code if isinstance(code, dict) else {'code': code})
    return orig_stamp(path, code, cfg, dest)


wm.simple_watermark_file = spy_stamp
r = c.post('/finish/')
wm.simple_watermark_file = orig_stamp
check('finish → done page', r.status_code == 302, f'{r.status_code}')
check('watermark ran for every photo', len(seen_infos) == len(before),
      f'{len(seen_infos)} vs {len(before)}')
if seen_infos:
    info = seen_infos[0]
    check('wm info: کد رایانه = 22241712', info.get('code') == '22241712', str(info))
    check('wm info: شماره پرونده present', bool(info.get('case_number')), str(info))
    check('wm info: نام کاربری = palireza', info.get('username') == 'palireza', str(info))
    check('wm info: تاریخ و ساعت (Jalali) present', bool(info.get('at')), str(info))
    check('wm info: base_url passed from request',
          (info.get('base_url') or '').startswith('http'), str(info))
rows = CaseImage.objects.filter(id__in=UPLOADED)
check('every row watermarked_at set', rows.count() == len(before)
      and all(i.watermarked_at for i in rows))
changed = 0
inked = 0
for path, old in before.items():
    if path.exists() and path.read_bytes() != old:
        changed += 1
    if path.exists():
        img = PILImage.open(path).convert('L')
        w, h = img.size
        # look at the third of the photo where the stamp actually lives
        where = (wm.config().get('POSITION') or 'bottom-right').lower()
        x0 = 0 if 'left' in where else w - w // 2
        y0 = 0 if 'top' in where else h - h // 3
        band = img.crop((x0, y0, x0 + w // 2, y0 + h // 3))
        dark = sum(1 for v in band.getdata() if v < 70)
        if dark > 150:
            inked += 1
check('every stamped file changed on disk', changed == len(before), f'{changed}/{len(before)}')
check('watermark ink visible on every image', inked == len(before), f'{inked}/{len(before)}')
strays = [p for p in (storage.root()).rglob('*')
          if p.is_file() and (p.name.endswith('.wm-tmp') or p.name.endswith('.upload'))]
check('only stamped files remain (no staging strays)', not strays, str(strays))

r = c.get(f'/media/serve/{rows.first().id}/')
check('serve no-store', 'no-store' in (r.get('Cache-Control') or ''), r.get('Cache-Control'))

print('== H. watermark overlay (unit) ==')
info = {'code': '22241712', 'case_number': '77777777', 'username': 'palireza',
        'at': '۱۴۰۵-۰۷-۰۹ ۱۲:۳۴', 'base_url': 'http://testserver/'}
lines = wm._stamp_lines(info)
expected_labeled = ['کد رایانه پرونده: 22241712', 'شماره پرونده: 77777777',
                    'نام کاربری: palireza', 'تاریخ و ساعت: ۱۴۰۵-۰۷-۰۹ ۱۲:۳۴']
check('stamp shows every value with its Persian label', lines == expected_labeled,
      str(lines))
check('labels are joined Persian words (shaped, RTL)',
      all(any('\u0600' <= ch <= '\u06ff' and ch.isalpha() for ch in l) for l in lines))
check('WATERMARK_LABELS_ENABLED=false restores the plain values',
      wm._stamp_lines(info, {'LABELS_ENABLED': False}) ==
      [info['code'], info['case_number'], info['username'], info['at']],
      str(wm._stamp_lines(info, {'LABELS_ENABLED': False})))
stamp = wm.simple_overlay((1280, 960), info)
check('overlay dict renders ink', stamp.getbbox() is not None)
check('overlay string (CLI) renders', wm.simple_overlay((1280, 960), '22241712').getbbox() is not None)
check('overlay partial dict renders', wm.simple_overlay((1280, 960), {'code': 'X1'}).getbbox() is not None)
check('overlay small image renders', wm.simple_overlay((400, 300), info).getbbox() is not None)

# v1.22 — the stamp is the *same share* of the photo at every resolution
# (that is what "consistent" means): the height stays inside the configured
# band and never wanders far between a tiny and a huge photo.
shares = {}
for size in ((230, 110), (320, 240), (1280, 960), (4000, 3000)):
    bb = wm.simple_overlay(size, info).getbbox()
    shares[size] = (bb[3] - bb[1]) / size[1]
for size, share in shares.items():
    check(f'stamp height share sane on {size[0]}x{size[1]} ({share*100:.0f}%)',
          0.2 <= share <= 0.42, f'{share:.2f}')
check('stamp proportion is consistent across resolutions',
      max(shares.values()) - min(shares.values()) <= 0.08, str(shares))

# v1.19 — QR only when scannable: record every _qr_image call
qr_calls = []
orig_qr_probe = wm._qr_image


def probe_qr(url, side, cfg=None):
    qr_calls.append(side)
    return orig_qr_probe(url, side, cfg)


wm._qr_image = probe_qr
try:
    wm.simple_overlay((230, 110), info)
    wm.simple_overlay((320, 240), info)
finally:
    wm._qr_image = orig_qr_probe
check('QR skipped on tiny photos', all(s >= 88 for s in qr_calls) if qr_calls else True,
      str(qr_calls))
qr_calls.clear()
wm._qr_image = probe_qr
try:
    wm.simple_overlay((1280, 960), info)
finally:
    wm._qr_image = orig_qr_probe
check('QR requested on big photos', qr_calls and qr_calls[0] >= 88, str(qr_calls))

qr_on = wm.simple_overlay((1280, 960), info)
qr_off = wm.simple_overlay((1280, 960), {**info, 'base_url': ''})


def dark_in(img, box):
    """Dark pixels of ``img`` over ``box`` — measured on a white canvas so the
    transparent RGBA background does not read as ink."""
    canvas = PILImage.new('RGBA', img.size, (255, 255, 255, 255))
    canvas.alpha_composite(img)
    reg = canvas.convert('L').crop(box)
    return sum(1 for v in reg.getdata() if v < 80)


# the block is anchored bottom-right; with a QR its height equals the QR side
# and the QR is the block's leftmost element → the left square of the ink bbox
def white_in(img, box):
    canvas = PILImage.new('RGBA', img.size, (0, 0, 0, 255))
    canvas.alpha_composite(img)
    reg = canvas.convert('L').crop(box)
    return sum(1 for v in reg.getdata() if v > 200)


bbox = qr_on.getbbox()
side = bbox[3] - bbox[1]
qr_box = (bbox[0], bbox[1], bbox[0] + side, bbox[3])
on_white = white_in(qr_on, qr_box)
off_white = white_in(qr_off, qr_box)
check('QR (white backing + dark modules) present when base_url set',
      on_white > 400 and dark_in(qr_on, qr_box) > 400,
      f'white={on_white} dark={dark_in(qr_on, qr_box)} box={qr_box}')
# the backing is a *filled* white plate: without base_url the same square holds
# only thin text strokes, i.e. far less white.
check('no QR block without base_url', off_white < on_white / 3,
      f'on_white={on_white} off_white={off_white}')
url = wm._wm_info_url(info)
check('_wm_info_url → wm_info route', '/wm-info/' in url and reverse('wm_info') == '/wm-info/')
check('_wm_info_url carries all params',
      all(k in url for k in ('c=', 'f=', 'u=', 't=')), url)
check('_wm_info_url empty without base_url', wm._wm_info_url({'code': 'x'}) == '')
check('_wm_info_url keeps ASCII digits (compact QR)',
      '%D9' not in url and '%DB' not in url, url)
img_qr = wm._qr_image(url, 120)
check('_qr_image builds a crisp QR square (≥ requested side)',
      img_qr is not None and img_qr.width == img_qr.height >= 120,
      str(getattr(img_qr, 'size', None)))
qr_arr = list(img_qr.getdata()) if img_qr is not None else []
check('_qr_image uses a white backing + black modules',
      any(px[3] > 200 and px[0] < 60 for px in qr_arr) and
      any(px[3] > 150 and px[0] > 200 for px in qr_arr))

# v1.20 — custom text + .env toggles
cfg_custom = {'CUSTOM_TEXT': 'HELLO 123', 'CUSTOM_TEXT_ENABLED': True}
check('custom text appended under the labeled values',
      wm._stamp_lines(info, cfg_custom) == expected_labeled + ['HELLO 123'])
check('custom text hidden when its toggle is off',
      wm._stamp_lines(info, {'CUSTOM_TEXT': 'HELLO', 'CUSTOM_TEXT_ENABLED': False}) ==
      expected_labeled)
check('empty custom text adds nothing',
      len(wm._stamp_lines(info, {'CUSTOM_TEXT': '   ', 'CUSTOM_TEXT_ENABLED': True})) == 4)
check('default config leaves the stamp at four lines', len(wm._stamp_lines(info)) == 4)

# Persian letter joining (presentation forms) — Latin passes through
shaped = wm._shape_text('بیمه دانا')
check('Persian custom text is shaped to joined forms',
      any(0xFE70 <= ord(ch) <= 0xFEFF for ch in shaped), repr(shaped))
check('Latin text passes through _shape_text unchanged',
      wm._shape_text('palireza 22241712') == 'palireza 22241712')

# QR toggle off → no QR even with base_url
qr_off_toggle = wm.simple_overlay((1280, 960), info, {'QR_ENABLED': False})
check('QR toggle off → no QR block', dark_in(qr_off_toggle, qr_box) < 50,
      f'dark={dark_in(qr_off_toggle, qr_box)}')
st5 = wm.simple_overlay((1280, 960), info, cfg_custom)
check('overlay with custom text renders ink', st5.getbbox() is not None)
check('custom text adds one more stamp line',
      len(wm._stamp_lines(info, cfg_custom)) == len(wm._stamp_lines(info)) + 1)

# v1.19 — save quality: the re-encode must stay near-lossless (4:4:4, q95).
# Compare the re-encoded photo against the once-encoded reference and exclude
# the stamp pixels themselves (they are the watermark, not an error).
import math  # noqa: E402

grad = PILImage.new('RGB', (200, 150))
gp = grad.load()
for y in range(150):
    for x in range(200):
        gp[x, y] = (x * 255 // 200, y * 255 // 150, (x + y) % 255)
tmp = TMP / 'quality_probe.jpg'
grad.save(tmp, format='JPEG', quality=95)
ref = PILImage.open(tmp).convert('RGB')
stamp_bb = wm.simple_overlay((200, 150), {'code': '99', 'base_url': ''}).getbbox()
wm.simple_watermark_file(tmp, {'code': '99', 'base_url': ''})
rt = PILImage.open(tmp).convert('RGB')
pa, pb = list(ref.getdata()), list(rt.getdata())
sq = 0
n = 0
for i, (ca, cb) in enumerate(zip(pa, pb)):
    x, y = i % 200, i // 200
    if stamp_bb and stamp_bb[0] - 2 <= x <= stamp_bb[2] + 2 \
            and stamp_bb[1] - 2 <= y <= stamp_bb[3] + 2:
        continue
    sq += (ca[0] - cb[0]) ** 2 + (ca[1] - cb[1]) ** 2 + (ca[2] - cb[2]) ** 2
    n += 1
psnr = 10 * math.log10(255 * 255 / max(sq / max(n, 1) / 3, 1e-9))
check('re-encode stays near-lossless (PSNR ≥ 40 dB)', psnr >= 40, f'psnr={psnr:.1f}')

print('== I. QR fail-safe (must never break the text watermark) ==')
import builtins  # noqa: E402

real_import = builtins.__import__


def no_qrcode(name, *a, **k):
    if name == 'qrcode':
        raise ImportError('simulated missing qrcode')
    return real_import(name, *a, **k)


builtins.__import__ = no_qrcode
try:
    s = wm.simple_overlay((1280, 960), info)
    check('missing qrcode package → text watermark ok', s.getbbox() is not None)
finally:
    builtins.__import__ = real_import
orig_qr = wm._qr_image
wm._qr_image = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
try:
    s = wm.simple_overlay((1280, 960), info)
    check('exploding QR → text watermark ok', s.getbbox() is not None)
finally:
    wm._qr_image = orig_qr
orig_url = wm._wm_info_url
wm._wm_info_url = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
try:
    s = wm.simple_overlay((1280, 960), info)
    check('exploding QR URL → text watermark ok', s.getbbox() is not None)
finally:
    wm._wm_info_url = orig_url

print('== J. /wm-info/ page ==')
r = anon.get('/wm-info/?c=22241712&f=77777777&u=palireza&t=1405-07-09_12:34')
check('wm-info 200 (short params, new QR)', r.status_code == 200)
body = r.content.decode()
for needle in ('22241712', '77777777', 'palireza', '1405-07-09', 'کد رایانه',
               'شماره پرونده', 'نام کاربری', 'تاریخ و ساعت',
               'dana-logo.png', 'hef.co.ir.png'):
    check(f'wm-info shows «{needle}»', needle in body)
check('wm-info without params 200', anon.get('/wm-info/').status_code == 200)
# photos stamped before v1.22 carry the long parameter names — still readable
old = anon.get('/wm-info/?code=22241712&case=77777777&user=palireza&at=1405-07-09%2012:34')
check('wm-info still reads pre-v1.22 long params',
      '22241712' in old.content.decode() and 'palireza' in old.content.decode())

print(f'\n== SUMMARY: {PASS} passed, {FAIL} failed ==')
sys.exit(1 if FAIL else 0)
