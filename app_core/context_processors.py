"""Context processors shared by all DANA templates."""
from django.conf import settings
from django.urls import reverse

#: v1.14 — the native browser Back button must act like **our own** back button:
#: each page declares where «بازگشت» leads and core.js routes popstate there.
BACK_URLS = {
    # v1.15 — back from the upload page = the نوع بیمه page (stage 2)
    'step2_upload': '/login/?stage=2',
    'step3_done': '/step2-upload/',
    'storage_index': '/step2-upload/',
    'storage_folder': '/step2-upload/',
}


def _session_timeout(request):
    """The countdown payload for the pages (v1.12) — safe when no session exists."""
    from app_account.middleware import session_remaining, timeout_config

    seconds, warn, mode = timeout_config()
    remaining = session_remaining(request) if seconds else 0
    payload = {
        'enabled': bool(seconds and remaining),
        'total': seconds,
        'remaining': remaining,
        'warn': warn,
        'mode': mode,
        'pingUrl': reverse('session_ping'),
        'timeoutUrl': '/?timeout=1',
        'logoutUrl': reverse('logout'),
        'label': f'{max(1, seconds // 60)} دقیقه',
    }
    return payload


def dana_context(request):
    """Expose the active color theme (per selected insurance type) to templates.

    The theme follows the case if one exists, otherwise the in-progress login
    state (stages 2–3 of the wizard).
    """
    insurance = (request.session.get('case') or {}).get('insurance_type')
    if not insurance:
        insurance = (request.session.get('login_state') or {}).get('insurance_type')
    if insurance == 'body':
        theme = 'badene'      # green palette — بیمه بدنه
    elif insurance == 'third':
        theme = 'satheth'     # pink palette — بیمه شخص ثالث مالی
    else:
        theme = 'default'     # brand teal (before selection)
    # v1.13 — development helpers: the tiny box in the footer that changes
    # CAR_IMAGE_MAX_GAP_SECONDS from inside the running app
    from . import dev_settings

    dev_tools = dev_settings.enabled()
    dev_gap = dev_settings.get(request, 'CAR_IMAGE_MAX_GAP_SECONDS')

    # v1.21 — the only image formats an upload may have (HEIC/HEIF, JPEG/JPG,
    # PNG, DNG): the «accept» attribute of every file input comes from here, so
    # the list lives in one place (app_media/services/formats.py).
    from app_media.services.formats import ACCEPT_ATTR

    # v1.21 — the header «خروج» button is gone; only the badge next to the
    # user's name exits the app. The session countdown stays on every page.
    auth = request.session.get('auth') or {}
    url_name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
    timeout = _session_timeout(request)
    import json

    return {
        'theme': theme,
        'has_case': bool((request.session.get('case') or {}).get('pk')),
        'has_session': bool(auth.get('username')),
        'session_username': auth.get('username', ''),
        'back_url': BACK_URLS.get(url_name, ''),
        'dev_tools': dev_tools,
        'dev_gap': dev_gap,
        'dev_gap_overridden': dev_settings.is_overridden(request, 'CAR_IMAGE_MAX_GAP_SECONDS'),
        # v1.21 — «accept» of every upload input (single list of formats)
        'ACCEPT_IMAGE': ACCEPT_ATTR,
        'session_timeout_json': json.dumps(timeout, ensure_ascii=False),
        # brand links (settings.BRAND_URLS) — logo links + footer
        'DANA_URL': getattr(settings, 'BRAND_URLS', {}).get('DANA_URL', 'https://www.dana-insurance.com/'),
        'HEF_URL': getattr(settings, 'BRAND_URLS', {}).get('HEF_URL', 'http://hef.co.ir'),
        # v1.21 — the logo FILES for templates/core/_brand_logos.html (the one
        # place that renders them; settings.BRAND_LOGOS ← .env)
        'DANA_LOGO': getattr(settings, 'BRAND_LOGOS', {}).get('DANA_LOGO', 'img/dana-logo.png'),
        'HEF_LOGO': getattr(settings, 'BRAND_LOGOS', {}).get('HEF_LOGO', 'img/hef.co.ir.png'),
        # v1.16 — the css/js cache-buster comes from settings.STATIC_VERSION
        # (bumped per release) — the templates no longer hardcode versions.
        'STATIC_VERSION': getattr(settings, 'STATIC_VERSION', '1.16'),
        # v1.23 — the version the footer prints (settings.APP_VERSION ← .env,
        # falling back to STATIC_VERSION).
        'APP_VERSION': getattr(settings, 'APP_VERSION', '') or getattr(settings, 'STATIC_VERSION', ''),
    }
