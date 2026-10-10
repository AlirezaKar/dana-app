"""
Django settings for the DANA Insurance case-registration & image-capture system.

- Persian RTL frontend, English backend (Persian verbose names).
- SQLite for development.
- Multi-app layout: app_core, app_account, app_records, app_main, app_media.

**Every tunable value lives in `.env`** (see `.env.sample` for the full list with
comments); this file only reads them through ``dana.env.Env``. A real environment
variable wins over the file, and ``DANA_<KEY>`` wins over ``<KEY>``, so a value can
be changed for a single run::

    DANA_CAR_IMAGE_MAX_GAP_SECONDS=3 python manage.py runserver

If `.env` is missing the project still starts with the defaults written below.
"""
from pathlib import Path

try:                                  # normal case: imported as «dana.settings»
    from .env import Env
except ImportError:                   # imported outside the package
    from dana.env import Env

BASE_DIR = Path(__file__).resolve().parent.parent

#: the configuration file (copy `.env.sample` to `.env` and edit it)
env = Env(BASE_DIR / '.env')


def _path(key, default):
    """A filesystem path from `.env`; relative values are taken from the project root."""
    value = env.get(key, '')
    path = Path(value) if value else Path(default)
    return path if path.is_absolute() else BASE_DIR / path

SECRET_KEY = env.get('SECRET_KEY', 'django-insecure-dana-dev-key-0f8c3d2a-change-me-in-production')

DEBUG = env.bool('DEBUG', True)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', ['*'])

# v1.22 — hardened cookies / TLS once DEBUG is off. Everything is env-driven and
# OFF by default so a plain-HTTP install (or the live preview) keeps working;
# behind a real TLS terminator set ENFORCE_HTTPS=True in `.env` and the app adds
# the secure/HTTPS headers and cookies for you.
if not DEBUG:
    SESSION_COOKIE_SAMESITE = 'Lax'
    CSRF_COOKIE_SAMESITE = 'Lax'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    if env.bool('ENFORCE_HTTPS', False):
        SECURE_SSL_REDIRECT = True
        SECURE_HSTS_SECONDS = 31536000
        SECURE_HSTS_INCLUDE_SUBDOMAINS = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # DANA apps
    'app_core',
    'app_account',
    'app_records',
    'app_main',
    'app_media',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # session timeout + activity log (v1.6 / v1.12) — keep this order
    'app_account.middleware.SessionTimeoutMiddleware',
    'app_account.middleware.UserActivityMiddleware',
]

# v1.21 — a production server (``manage.py serve`` → waitress) does not serve
# ``/static/`` the way ``runserver`` does; WhiteNoise serves it straight from
# STATIC_ROOT. Guarded, so an install without the package still starts.
try:
    import whitenoise  # noqa: F401
except ImportError:                          # pragma: no cover
    pass
else:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'dana.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'app_core.context_processors.dana_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'dana.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': _path('SQLITE_NAME', 'db.sqlite3'),
    }
}

# No password-based authentication in this version (see spec.md, assumption A1):
# the "login" is user-type + insurance-type + a record-matching identifier.
AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = env.get('LANGUAGE_CODE', 'fa-IR')

TIME_ZONE = env.get('TIME_ZONE', 'Asia/Tehran')

USE_I18N = True

USE_TZ = True

STATIC_URL = env.get('STATIC_URL', '/static/')

#: v1.16 — one main folder for every static asset (owner request):
#: ``statics/{css,js,font,img}`` hold the sources; ``python manage.py
#: collectstatic`` merges the rest (``statics/admin/``, Django admin's files)
#: into the very same folder (STATIC_ROOT == the sources' parent, exposed
#: through per-prefix finder entries).
STATIC_SOURCES = BASE_DIR / 'statics'
STATICFILES_DIRS = [
    ('css', STATIC_SOURCES / 'css'),
    ('js', STATIC_SOURCES / 'js'),
    ('font', STATIC_SOURCES / 'font'),
    ('img', STATIC_SOURCES / 'img'),
]
STATIC_ROOT = _path('STATIC_ROOT', STATIC_SOURCES)

#: cache-buster for css/js links (`?v=…`) — bump on every release that changes
#: static assets so browsers never keep an old copy (single source of truth;
#: the templates no longer hardcode versions).
STATIC_VERSION = env.get('STATIC_VERSION', '1.21')

# v1.22 — let WhiteNoise send a Cache-Control on /static/ in production; every
# css/js/logo link carries ?v=STATIC_VERSION, so a release bumps the version and
# busts the cache while browsers still revalidate between releases. Dev stays at
# 0 so template/asset edits are always picked up.
WHITENOISE_MAX_AGE = 0 if DEBUG else 3600

# v1.18 — absolute base URL for the watermark QR target when the request cannot
# provide one (management commands). Empty → the QR is skipped, never broken.
PUBLIC_BASE_URL = env.get('PUBLIC_BASE_URL', '')

# v1.21 — the production server started by ``python manage.py serve``
# (waitress — a real WSGI server, so no «development server» warning).
SERVER = {
    'HOST': env.get('SERVER_HOST', '0.0.0.0'),
    'PORT': env.int('SERVER_PORT', 8000),
    'THREADS': env.int('SERVER_THREADS', 8),
}

# Root directory for uploaded case images (final + temporary), located in the
# project root as required by the specification.
STORAGE_ROOT = _path('STORAGE_ROOT', 'storage')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# DANA app configuration — read from `.env` (see `.env.sample`)
# ---------------------------------------------------------------------------
BRAND_URLS = {
    'DANA_URL': env.get('DANA_URL', 'https://www.dana-insurance.com/'),
    # changed by the owner's manual template edit (was http://hef.co.ir)
    'HEF_URL': env.get('HEF_URL', 'http://127.0.0.1:6060'),
}

# v1.21 — the logo FILES, also from `.env`, in ONE place: pages render them
# through templates/core/_brand_logos.html and the watermark reads the same two
# names (WATERMARK.LOGOS falls back to them). Replace a file — or point
# DANA_LOGO / HEF_LOGO at another path under static/ — and everything changes.
BRAND_LOGOS = {
    'DANA_LOGO': env.get('DANA_LOGO', 'img/dana-logo.png'),
    'HEF_LOGO': env.get('HEF_LOGO', 'img/hef.co.ir.png'),
}

DANA = {
    # Car-shoot timing validation (see spec.md C5/C6):
    # the chassis photo(s) + the four car views form one "car group".
    'CAR_IMAGE_MAX_GAP_SECONDS': env.int('CAR_IMAGE_MAX_GAP_SECONDS', 10),
    'CAR_IMAGE_MAX_SPAN_MINUTES': env.int('CAR_IMAGE_MAX_SPAN_MINUTES', 10),
    # Re-import the Excel files from storage/data/ on every server (re)start.
    'AUTO_SYNC_EXCEL_ON_START': env.bool('AUTO_SYNC_EXCEL_ON_START', True),
    # Re-import them again whenever the data files changed and an info page is
    # opened (GET) — replaces having to run `manage.py seed_sample_data` by hand.
    'AUTO_SYNC_ON_PAGE_VIEW': env.bool('AUTO_SYNC_ON_PAGE_VIEW', True),
    # Log user activity (page views + every action) into UserActivity.
    'ACTIVITY_LOG': env.bool('ACTIVITY_LOG', True),
    # --- development helpers (the tiny box in the footer) -------------------
    'DEV_TOOLS': env.bool('DEV_TOOLS', DEBUG),
    # --- session timeout (v1.12) -------------------------------------------
    # After this many seconds without activity the session ends automatically:
    # the page shows a countdown popup («ادامهٔ کار» / «خروج») and then the user
    # is sent back to the login page. Any request refreshes the timer.
    'SESSION_TIMEOUT_SECONDS': env.int('SESSION_TIMEOUT_SECONDS', 600,
                                       aliases=('DANA_TIMEOUT_SECONDS',)),
    'SESSION_TIMEOUT_WARN_SECONDS': env.int('SESSION_TIMEOUT_WARN_SECONDS', 15,
                                            aliases=('DANA_TIMEOUT_WARN_SECONDS',)),
    # 'idle'     → counted from the last request (any click/page keeps you in)
    # 'absolute' → counted from the moment of login, no matter what you do
    'SESSION_TIMEOUT_MODE': env.get('SESSION_TIMEOUT_MODE', 'idle',
                                    aliases=('DANA_TIMEOUT_MODE',)),
}

# ---------------------------------------------------------------------------
# Watermark stamp burned into every stored photo (app_media/services/watermark.py)
# ---------------------------------------------------------------------------
WATERMARK = {
    'ENABLED': env.bool('WATERMARK_ENABLED', True),   # False = store the raw upload
    'POSITION': env.get('WATERMARK_POSITION', 'bottom-right'),
    'OPACITY': env.float('WATERMARK_OPACITY', 0.85),  # no background box
    'SCALE': env.float('WATERMARK_SCALE', 1.0),       # 1.0 = font ≈ 2.6 % of the short side
    'MIN_WIDTH_FRACTION': env.float('WATERMARK_MIN_WIDTH_FRACTION', 0.55),
    'LOGOS': env.list('WATERMARK_LOGOS', [BRAND_LOGOS['DANA_LOGO'], BRAND_LOGOS['HEF_LOGO']]),
    # v1.14 — logos + the six text lines only (no GPS, no maps URL); the same
    # facts are written into the image metadata (Windows: Properties → Details →
    # Comments) next to the stamp. The file name is the **field name** the photo
    # was uploaded for (car_card_front.jpg, …) — decided by the storage layer.
    'WRITE_COMMENT': env.bool('WATERMARK_WRITE_COMMENT', True),
    # v1.20 — custom text + on/off toggles (see .env.sample)
    'CUSTOM_TEXT': env.get('WATERMARK_CUSTOM_TEXT', ''),
    'CUSTOM_TEXT_ENABLED': env.bool('WATERMARK_CUSTOM_TEXT_ENABLED', True),
    'QR_ENABLED': env.bool('WATERMARK_QR_ENABLED', True),
    # v1.22 — the stamp is assembled from layers and every size is a *share* of
    # the photo, so the same stamp looks identical at any resolution. All
    # proportions are tunable here (or from `.env`); see `.env.sample`.
    'LOGO_WIDTH_FRACTION': env.float('WATERMARK_LOGO_WIDTH_FRACTION', 0.15),
    'QR_SIZE_FRACTION': env.float('WATERMARK_QR_SIZE_FRACTION', 0.10),
    'FONT_HEIGHT_FRACTION': env.float('WATERMARK_FONT_HEIGHT_FRACTION', 0.032),
    'MARGIN_FRACTION': env.float('WATERMARK_MARGIN_FRACTION', 0.02),
    'MAX_HEIGHT_FRACTION': env.float('WATERMARK_MAX_HEIGHT_FRACTION', 0.38),
    'QR_MIN_MODULE_PX': env.int('WATERMARK_QR_MIN_MODULE_PX', 3),
}
