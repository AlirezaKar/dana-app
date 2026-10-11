"""check_env.py — prove that `.env` is read the way the README promises (v1.23).

Run (Windows-safe, no shell scripts):
    .venv/bin/python scripts/check_env.py

Level 1  the reader alone (`dana/env.py`) against a throw-away file: both
         spellings (`KEY` / `DANA_KEY`), the doubled `DANA_DANA_LOGO` form, the
         precedence (real environment > file > default), aliases, quotes,
         `export`, trailing comments, empty = default, the "nobody reads this
         line" report and `reload()`.
Level 2  the real application: a temporary `.env` is fed to Django through
         `DANA_ENV_FILE` (the real `.env` is never touched) and the values are
         checked where the owner sees them — the footer version, `HEF_URL`, the
         logo file, the `?v=` cache-buster, the timing rule in the footer box and
         the watermark custom text.

Kept in git (``scripts/``) next to ``smoke23.py`` so an environment wipe cannot
lose it; it writes only into the system temp folder.
"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PASS, FAIL = 0, 0


def check(label, cond, extra=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f'  ok  {label}')
    else:
        FAIL += 1
        print(f'FAIL  {label}  {extra}')


# --------------------------------------------------------------------------- #
# level 1 — the reader
# --------------------------------------------------------------------------- #
sys.path.insert(0, str(REPO))
from dana.env import Env, candidate_names  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix='dana-env-'))
SAMPLE = TMP / 'sample.env'
SAMPLE.write_text(
    '# a comment line\n'
    '\n'
    'DANA_HEF_URL=http://91.92.207.127\n'          # the spelling .env.sample uses
    'DANA_CAR_IMAGE_MAX_GAP_SECONDS=3  # seconds\n'
    'DANA_DANA_LOGO=img/custom-dana.png\n'         # the old doubled spelling
    'DANA_STATIC_VERSION=7.7\n'
    'APP_VERSION=2.5.0\n'                          # the bare spelling
    'BARE_VALUE="a quoted value"\n'
    'export EXPORTED=yes\n'
    'DANA_EMPTY=\n'
    'DANA_LOGOZ=typo.png\n'                        # nobody asks for this
    'DANA_TIMEOUT_SECONDS=777\n'                   # an alias of SESSION_TIMEOUT_SECONDS
    'ONLY_HERE=file-value\n',
    encoding='utf-8')

print('== 1. the reader (dana/env.py) ==')
check('candidate names: DANA_<KEY> wins over <KEY>',
      candidate_names('HEF_URL') == ('DANA_HEF_URL', 'HEF_URL'))
check('candidate names: a prefixed key still tries the doubled form',
      candidate_names('DANA_LOGO') == ('DANA_DANA_LOGO', 'DANA_LOGO'))

f = Env(SAMPLE, environ={})
check('DANA_HEF_URL is read (was the bug)', f.get('HEF_URL') == 'http://91.92.207.127',
      repr(f.get('HEF_URL')))
check('DANA_CAR_IMAGE_MAX_GAP_SECONDS is read as an int',
      f.int('CAR_IMAGE_MAX_GAP_SECONDS', 10) == 3, repr(f.int('CAR_IMAGE_MAX_GAP_SECONDS', 10)))
check('a trailing "  # comment" is stripped',
      f.get('CAR_IMAGE_MAX_GAP_SECONDS') == '3', repr(f.get('CAR_IMAGE_MAX_GAP_SECONDS')))
check('the doubled DANA_DANA_LOGO spelling is read',
      f.get('DANA_LOGO', 'default.png') == 'img/custom-dana.png',
      repr(f.get('DANA_LOGO', 'default.png')))
check('the bare spelling is read too', f.get('APP_VERSION') == '2.5.0')
check('quoted values lose their quotes', f.get('BARE_VALUE') == 'a quoted value')
check('export KEY=value works', f.get('EXPORTED') == 'yes')
check('KEY= keeps the default', f.get('EMPTY', 'fallback') == 'fallback')
check('an unknown key keeps the default', f.get('NOT_THERE', 'fallback') == 'fallback')
check('an alias is read (DANA_TIMEOUT_SECONDS)',
      f.int('SESSION_TIMEOUT_SECONDS', 600, aliases=('DANA_TIMEOUT_SECONDS',)) == 777,
      repr(f.int('SESSION_TIMEOUT_SECONDS', 600, aliases=('DANA_TIMEOUT_SECONDS',))))
check('the source of a value is reported',
      f.source('HEF_URL')[:2] == ('file', 'DANA_HEF_URL'), repr(f.source('HEF_URL')))
_unused = f.unused_file_keys()
check('a line nobody reads is flagged (and a read one is not)',
      'DANA_LOGOZ' in _unused and 'DANA_HEF_URL' not in _unused, repr(_unused))

# precedence: the real environment beats the file, both spellings
for environ in ({'DANA_HEF_URL': 'http://env.example'}, {'HEF_URL': 'http://env2.example'}):
    e = Env(SAMPLE, environ=environ)
    check(f'environment beats the file ({sorted(environ)[0]})',
          e.get('HEF_URL') == list(environ.values())[0], repr(e.get('HEF_URL')))
check('an environment alias beats the file too',
      Env(SAMPLE, environ={'DANA_TIMEOUT_SECONDS': '42'})
      .int('SESSION_TIMEOUT_SECONDS', 600, aliases=('DANA_TIMEOUT_SECONDS',)) == 42)

# a key written twice: the DANA_ spelling wins
DOUBLE = TMP / 'double.env'
DOUBLE.write_text('ONLY_HERE=bare\nDANA_ONLY_HERE=prefixed\n', encoding='utf-8')
d = Env(DOUBLE, environ={})
check('a doubled key: DANA_ wins', d.get('ONLY_HERE') == 'prefixed', repr(d.get('ONLY_HERE')))
check('a doubled key is reported', d.shadowed_file_keys() == [('ONLY_HERE', 'DANA_ONLY_HERE')],
      repr(d.shadowed_file_keys()))

# a restart reads the new content — that is what "restart applies the .env" means
SAMPLE.write_text('DANA_HEF_URL=http://changed.example\n', encoding='utf-8')
check('reload() re-reads the file (a restart does the same)',
      Env(SAMPLE, environ={}).reload().get('DANA_HEF_URL') == 'http://changed.example')

# --------------------------------------------------------------------------- #
# level 2 — the application, fed with the same kind of file
# --------------------------------------------------------------------------- #
print('== 2. the application (Django) ==')
APP_ENV = TMP / 'app.env'
APP_ENV.write_text(
    'DANA_APP_VERSION=9.9.9\n'
    'DANA_STATIC_VERSION=8.8\n'
    'DANA_HEF_URL=http://91.92.207.127\n'
    'DANA_LOGO=img/custom-logo.png\n'
    'DANA_CAR_IMAGE_MAX_GAP_SECONDS=3\n'
    'DANA_DEBUG=True\n'
    'DANA_DEV_TOOLS=True\n'
    'DANA_WATERMARK_CUSTOM_TEXT=متن سفارشی\n'
    'DANA_DB_PATH=db.sqlite3\n',
    encoding='utf-8')

PROBE = r'''
import json, os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dana.settings')
django.setup()
from django.conf import settings
from django.test import Client
r = Client().get('/login/')
html = r.content.decode('utf-8')
print(json.dumps({
    'status': r.status_code,
    'APP_VERSION': settings.APP_VERSION,
    'STATIC_VERSION': settings.STATIC_VERSION,
    'HEF_URL': settings.BRAND_URLS['HEF_URL'],
    'DANA_LOGO': settings.BRAND_LOGOS['DANA_LOGO'],
    'gap': settings.DANA['CAR_IMAGE_MAX_GAP_SECONDS'],
    'custom_text': settings.WATERMARK['CUSTOM_TEXT'],
    'db': str(settings.DATABASES['default']['NAME']),
    'env_file': str(settings.ENV_FILE),
    'html': {
        'footer_version': 'ver: 9.9.9' in html,
        'hef_link': 'href="http://91.92.207.127"' in html,
        'logo': 'img/custom-logo.png' in html,
        'cache_buster': '?v=8.8' in html,
        'gap_box': 'value="3"' in html,
    },
}))
'''

# what the project's own `.env` holds right now — it must come out unchanged
REAL_ENV = REPO / '.env'
real_before = REAL_ENV.read_text(encoding='utf-8') if REAL_ENV.exists() else None

os.environ.pop('DANA_ENV_FILE', None)
proc = subprocess.run([sys.executable, '-c', PROBE], cwd=str(REPO), capture_output=True,
                      text=True, env={**os.environ, 'DANA_ENV_FILE': str(APP_ENV)})
if proc.returncode != 0:
    check('the app starts with DANA_ENV_FILE', False, proc.stderr.strip()[-400:])
else:
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    check('the app starts with another config file', out['status'] == 200)
    check('DANA_ENV_FILE points at that file', out['env_file'] == str(APP_ENV), out['env_file'])
    check('settings.APP_VERSION ← DANA_APP_VERSION', out['APP_VERSION'] == '9.9.9', out['APP_VERSION'])
    check('settings.STATIC_VERSION ← DANA_STATIC_VERSION', out['STATIC_VERSION'] == '8.8')
    check('settings.BRAND_URLS ← DANA_HEF_URL', out['HEF_URL'] == 'http://91.92.207.127')
    check('settings.BRAND_LOGOS ← DANA_LOGO', out['DANA_LOGO'] == 'img/custom-logo.png')
    check('settings.DANA ← DANA_CAR_IMAGE_MAX_GAP_SECONDS', out['gap'] == 3, repr(out['gap']))
    check('settings.WATERMARK ← DANA_WATERMARK_CUSTOM_TEXT',
          out['custom_text'] == 'متن سفارشی', repr(out['custom_text']))
    check('settings.DATABASES ← DANA_DB_PATH', out['db'].endswith('db.sqlite3'), out['db'])
    check('footer prints the version from .env', out['html']['footer_version'])
    check('footer link uses HEF_URL from .env', out['html']['hef_link'])
    check('the page renders the logo file from .env', out['html']['logo'])
    check('css/js/logos are cache-busted with .env version', out['html']['cache_buster'])
    check('the footer box shows the .env timing rule', out['html']['gap_box'])

# the project's own .env was never touched by any of this
real_after = REAL_ENV.read_text(encoding='utf-8') if REAL_ENV.exists() else None
check("the project's own .env is untouched", real_after == real_before)

print()
print(f'== SUMMARY: {PASS} passed, {FAIL} failed ==')
sys.exit(1 if FAIL else 0)
