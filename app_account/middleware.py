"""Request middleware: the session timeout and the page-visit log.

``SessionTimeoutMiddleware`` (v1.12) ends the app session automatically after
``DANA['SESSION_TIMEOUT_SECONDS']`` (default 10 minutes) — measured from the last
request in ``'idle'`` mode or from the login in ``'absolute'`` mode. The page
itself shows a countdown popup before that (``app_core/static/js/core.js`` →
``DANA.initTimeout``) and can push the deadline away with
``/session/ping/`` («ادامهٔ کار»), but the server is authoritative: an expired
session is closed here and the user lands on the login page.

``UserActivityMiddleware`` (v1.6) appends one ``page_view`` row per meaningful
page load — authenticated or anonymous.
"""
from datetime import timedelta

from django.conf import settings
from django.shortcuts import redirect
from django.utils import timezone

from .activity import NON_PAGE_ROUTES, log_activity, resolve_page_location

#: path prefixes that are never logged
SKIP_PREFIXES = ('/static/', '/media/', '/admin/', '/favicon', '/__debug__/')


class UserActivityMiddleware:
    """Append a ``page_view`` row after the response has been produced."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self.record(request, response)
        except Exception:              # logging must never break a request
            pass
        return response

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def enabled():
        return getattr(settings, 'DANA', {}).get('ACTIVITY_LOG', True)

    @classmethod
    def should_log(cls, request, response=None):
        if not cls.enabled():
            return False
        if request.method != 'GET':
            return False            # page views only (POSTs are logged by their own views)
        path = request.path or ''
        if path.startswith(SKIP_PREFIXES):
            return False
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return False
        if response is not None and getattr(response, 'status_code', 200) >= 400:
            return False            # don't log error pages / redirects
        name = getattr(getattr(request, 'resolver_match', None), 'url_name', '') or ''
        if name in NON_PAGE_ROUTES:
            return False
        if getattr(request, 'path', '').startswith('/step3-done'):
            # keep the final page — it is a real page even though it is reached late
            return True
        return True

    @classmethod
    def record(cls, request, response=None):
        if not cls.should_log(request, response):
            return None
        _url_name, page_label = resolve_page_location(request.path)
        return log_activity(
            'page_view',
            request=request,
            description=page_label or 'بازدید صفحه',
            object_label=page_label,
        )


# --------------------------------------------------------------------------- #
# v1.12 — the 10-minute session timeout
# --------------------------------------------------------------------------- #
def _parse(value):
    """ISO string / datetime → aware datetime (or ``None``)."""
    if not value:
        return None
    if isinstance(value, str):
        try:
            return timezone.datetime.fromisoformat(value)
        except ValueError:
            return None
    return value


def timeout_config():
    """``(seconds, warn_seconds, mode)`` from ``settings.DANA``."""
    cfg = getattr(settings, 'DANA', {}) or {}
    seconds = int(cfg.get('SESSION_TIMEOUT_SECONDS', 600) or 0)
    warn = int(cfg.get('SESSION_TIMEOUT_WARN_SECONDS', 15) or 0)
    mode = str(cfg.get('SESSION_TIMEOUT_MODE', 'idle') or 'idle').lower()
    return seconds, warn, mode


def session_reference(auth, mode):
    """The moment the countdown is measured from (login time or last request)."""
    if mode == 'absolute':
        return _parse(auth.get('at')) or _parse(auth.get('last_seen'))
    return _parse(auth.get('last_seen')) or _parse(auth.get('at'))


def session_remaining(request):
    """Seconds left in the app session, or ``0`` when there is none/expired."""
    seconds, _warn, mode = timeout_config()
    if not seconds:
        return 0
    auth = (request.session.get('auth') or {}) if hasattr(request, 'session') else {}
    if not auth:
        return 0
    reference = session_reference(auth, mode)
    if reference is None:
        return seconds
    elapsed = (timezone.now() - reference).total_seconds()
    return max(0, int(seconds - elapsed))


def close_session(request, seconds=None, mode=None, log=True):
    """End the app session: forget the login, the wizard state and the case.

    Called by the middleware when the server clock has run out and by the login
    view when the browser reached the end of its own countdown first. Returns the
    name of the user that was logged in (empty when nobody was).
    """
    auth = request.session.get('auth') or {}
    username = auth.get('username', '')
    if not username:
        return ''
    seconds, _warn, mode = timeout_config() if seconds is None else (seconds, None, mode)
    if log:
        log_activity('session_timeout', request=request, username=username,
                     user_type=auth.get('user_type', ''),
                     description=f'پایان خودکار نشست پس از {max(1, seconds // 60)} دقیقه '
                                 + ('بی‌فعالیتی' if mode != 'absolute' else 'حضور در سامانه'))
    for key in ('auth', 'login_state', 'case'):
        request.session.pop(key, None)
    request.session['timed_out'] = True
    request.session.modified = True
    return username


def is_ajax(request):
    """True for the app's own background requests (fetch/XHR)."""
    return (request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or (request.headers.get('Accept') or '').startswith('application/json'))


class SessionTimeoutMiddleware:
    """Close the app session when its time is up (spec.md v1.12).

    The AJAX ping (``/session/ping/``) is a normal request, so it refreshes the
    deadline in ``'idle'`` mode — that is what the «ادامهٔ کار» button uses.

    v1.21 — an expired **background** request answers with JSON (HTTP 401)
    instead of a redirect: a fetch() call cannot follow a redirect into an HTML
    login page and used to die with «خطا در ارتباط با سرور» while the browser
    stayed on a dead page. The script now sees the 401 and walks the user back
    to the login page itself.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expired = False
        try:
            expired = self._expired(request)
            if not expired:
                self._touch(request)
        except Exception:              # never break a request because of the timer
            expired = False
        if expired:
            if is_ajax(request):
                from django.http import JsonResponse
                return JsonResponse({
                    'ok': False, 'session_expired': True, 'remaining': 0,
                    'error': 'مهلت نشست شما به پایان رسید.',
                    'login_url': '/?timeout=1',
                }, status=401)
            return redirect('/?timeout=1')
        return self.get_response(request)

    @staticmethod
    def _expired(request):
        seconds, _warn, mode = timeout_config()
        if not seconds or not hasattr(request, 'session'):
            return False
        auth = request.session.get('auth') or {}
        if not auth:
            return False
        reference = session_reference(auth, mode)
        if reference is None:
            return False
        if (timezone.now() - reference) < timedelta(seconds=seconds):
            return False

        # ---- time is up: close the session -------------------------------
        close_session(request, seconds=seconds, mode=mode)
        return True

    @staticmethod
    def _touch(request):
        """Mark this request as activity (drives the countdown the pages show)."""
        seconds, _warn, mode = timeout_config()
        if not seconds or not hasattr(request, 'session'):
            return
        auth = request.session.get('auth') or {}
        if not auth:
            return
        auth['last_seen'] = timezone.now().isoformat()
        auth.setdefault('at', auth['last_seen'])
        request.session['auth'] = auth
        request.session.modified = True
