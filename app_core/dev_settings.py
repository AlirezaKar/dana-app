"""Live-overridable settings for development (v1.13).

Some values normally come from `.env` / ``settings.DANA`` are also editable from
inside the running app, so a developer can try a different rule without touching
a file or restarting the server. The override is kept in the **session**, so it
belongs to that operator and disappears when the session ends; the configuration
in `.env` is never modified.

The fast value lives in the tiny unlabeled box in the footer of the page right
before the upload page (see ``base.html`` → ``footer_extra`` and
``app_account/templates/account/login.html``), and the endpoint is
``/dev/setting/`` (``app_core/views.py``).

Everything is off unless ``DEV_TOOLS`` is true (`.env` → ``DEV_TOOLS=True``);
set it to ``False`` on a real installation.
"""
from django.conf import settings

#: session key holding ``{setting_key: value}``
SESSION_KEY = 'dev_settings'

#: the settings that may be changed from the UI — key → rules
EDITABLE = {
    'CAR_IMAGE_MAX_GAP_SECONDS': {
        'type': int, 'min': 1, 'max': 3600,
        'label': 'حداکثر فاصلهٔ بین دو تصویر پیاپی «اطراف ماشین و شماره شاسی ماشین» (ثانیه)',
    },
    'CAR_IMAGE_MAX_SPAN_MINUTES': {
        'type': int, 'min': 1, 'max': 600,
        'label': 'مهلت کل عکس‌برداری «اطراف ماشین و شماره شاسی ماشین» (دقیقه)',
    },
}


def enabled():
    """Are the development helpers switched on (``.env`` → ``DEV_TOOLS``)?"""
    return bool((getattr(settings, 'DANA', {}) or {}).get('DEV_TOOLS'))


def overrides(request):
    if request is None or not hasattr(request, 'session'):
        return {}
    return dict(request.session.get(SESSION_KEY) or {})


def get(request, key):
    """The value in force: session override → `.env` / ``settings.DANA``."""
    configured = (getattr(settings, 'DANA', {}) or {}).get(key)
    value = overrides(request).get(key)
    return configured if value in (None, '') else value


def is_overridden(request, key):
    return overrides(request).get(key) not in (None, '')


def set_value(request, key, raw):
    """Store an override. Returns ``(ok, value, error)``.

    An empty ``raw`` removes the override, so the value falls back to `.env` —
    which is what the tiny footer box does when it is emptied.
    """
    rules = EDITABLE.get(key)
    if rules is None:
        return False, None, 'این تنظیم از داخل برنامه قابل تغییر نیست.'
    if request is None or not hasattr(request, 'session'):
        return False, None, 'نشست یافت نشد.'

    raw = ('' if raw is None else str(raw)).strip()
    store = dict(request.session.get(SESSION_KEY) or {})
    if not raw:                                   # clear → back to the config
        store.pop(key, None)
        request.session[SESSION_KEY] = store
        request.session.modified = True
        return True, (getattr(settings, 'DANA', {}) or {}).get(key), None

    try:
        value = rules['type'](raw)
    except (TypeError, ValueError):
        return False, None, 'مقدار وارد‌شده معتبر نیست (عدد لازم است).'
    if not (rules.get('min', value) <= value <= rules.get('max', value)):
        return False, None, (f'مقدار باید بین {rules.get("min")} و {rules.get("max")} باشد.')

    store[key] = value
    request.session[SESSION_KEY] = store
    request.session.modified = True
    return True, value, None
