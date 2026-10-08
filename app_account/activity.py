"""User-activity logging (spec.md v1.6).

Every meaningful action of a user (or anonymous visitor) is appended to
``app_account.models.UserActivity`` — an **append-only** log that is read-only in
the Django admin.

Rules (see SKILL.md «django-user-activity-logs»):
  * the entry is written by the **view/middleware that owns the event** — never
    from the admin;
  * logging must never break a request: every write is wrapped and swallowed;
  * Persian labels, newest-first ordering, ``created_at = timezone.now``;
  * raw strings are truncated to the field lengths before saving;
  * aggregate counters are bumped atomically with ``F() + 1``.

Writers
-------
======================  ===================================================
page_view               ``app_account.middleware.UserActivityMiddleware`` (GET)
login_success/_failed   ``app_account.views.login`` → ``record_login_attempt()``
logout                  ``app_account.views.logout``
insurance_select        ``app_account.views.login`` (stage 2)
record_match            ``app_account.views.login`` (stage 3)
image_upload/_remove    ``app_media.views``
car_confirm             ``app_media.views.confirm_car``
finish                  ``app_main.views.finish``
======================  ===================================================
"""
import logging

from django.db.models import F
from django.urls import NoReverseMatch, resolve
from django.utils import timezone

from .utils import get_client_ip, truncate

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# Persian labels for the pages (fall back to the raw path when a route is new)
# --------------------------------------------------------------------------
PAGE_LABELS = {
    'login': 'ورود به سامانه',
    'login_post': 'ورود به سامانه',
    'logout': 'خروج از حساب',
    'check_user': 'بررسی حساب کاربری',
    'session_ping': 'تمدید نشست',
    'step2_upload': 'یافتن پرونده و بارگذاری تصاویر',
    'case_resolve': 'یافتن پرونده',
    'victim_add': 'افزودن زیان‌دیده',
    'victim_remove': 'حذف زیان‌دیده',
    'step3_done': 'پایان و شمارهٔ یکتا',
    'finish': 'اتمام و ساخت پوشه',
    'restart': 'شروع دوباره',
    'records_search': 'جست‌وجوی شناسه‌ها',
    'records_details': 'اطلاعات پرونده',
    'media_upload': 'بارگذاری تصویر',
    'media_remove': 'حذف تصویر',
    'media_confirm_group': 'تأیید بخش تصاویر',
    'media_serve': 'نمایش تصویر',
    'storage_index': 'مشاهدهٔ پوشهٔ ذخیره‌سازی',
    'storage_folder': 'جزئیات پوشهٔ ذخیره‌سازی',
    'storage_raw': 'نمایش فایل ذخیره‌سازی',
}

#: routes that are AJAX/non-page views — never logged as a page view
NON_PAGE_ROUTES = {
    'records_search', 'records_details', 'check_user', 'session_ping',
    'media_upload', 'media_remove', 'media_confirm_group', 'media_serve',
    'storage_raw', 'case_resolve', 'victim_add', 'victim_remove',
    'finish', 'logout', 'restart',
}


def resolve_page_location(path):
    """Return ``(url_name, page_label)`` for a request path (Persian label)."""
    try:
        match = resolve(path)
    except Exception:
        return '', ''
    url_name = match.view_name or ''
    try:
        url_name = match.namespace + ':' + match.url_name if match.namespace else url_name
    except Exception:
        pass
    label = PAGE_LABELS.get(getattr(match, 'url_name', '') or '', '')
    return truncate(url_name, 200), truncate(label, 200)


# --------------------------------------------------------------------------
# Resolving "who is this?" — the app keeps its own session identity
# --------------------------------------------------------------------------
def _resolve_request_user(request):
    """The account behind the request, or ``None``.

    1. Django's ``request.user`` when a real auth session exists (admin, etc.).
    2. otherwise the app's own login session: ``request.session['auth']['username']``.
    The result is cached on the request so one request costs at most one query.
    """
    if request is None:
        return None
    cached = getattr(request, '_activity_user', 'unset')
    if cached != 'unset':
        return cached

    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        request._activity_user = user
        return user

    auth = {}
    try:
        auth = request.session.get('auth') or {}
    except Exception:
        auth = {}
    if not auth.get('username'):
        request._activity_user = None
        return None

    from .services import find_user
    try:
        user = find_user(auth.get('username'))
    except Exception:
        user = None
    request._activity_user = user
    return user


def request_identity(request):
    """``(user, username_label, user_type)`` for the current request."""
    user = _resolve_request_user(request)
    auth = {}
    try:
        auth = request.session.get('auth') or {}
    except Exception:
        auth = {}
    if user is not None:
        profile = getattr(user, 'profile', None)
        return user, user.get_username(), (profile.user_type if profile else '')
    username = auth.get('username') or ''
    return None, (username or 'anonymous'), auth.get('user_type', '')


# --------------------------------------------------------------------------
# The writer
# --------------------------------------------------------------------------
def log_activity(action, *, request=None, user=None, username='', user_type='',
                 description='', object_label='', method=''):
    """Append one row to the activity log. Returns the row or ``None``.

    Never raises — a logging problem must not break the request.
    """
    try:
        from .models import UserActivity

        if user is None and request is not None:
            user, auto_username, auto_type = request_identity(request)
            username = username or auto_username
            user_type = user_type or auto_type
        elif user is not None:
            profile = getattr(user, 'profile', None)
            username = username or user.get_username()
            user_type = user_type or (profile.user_type if profile else '')

        if not username:
            username = 'anonymous'

        row = UserActivity.objects.create(
            user=user,
            username_label=truncate(username, 150),
            user_type=user_type or '',
            action=action,
            description=truncate(description, 300),
            object_label=truncate(object_label, 200),
            path=truncate(getattr(request, 'path', '') if request else '', 500),
            url_name=truncate(getattr(getattr(request, 'resolver_match', None),
                                      'view_name', '') if request else '', 200),
            page_label=truncate(resolve_page_location(request.path)[1] if request else '', 200),
            method=truncate(method or (getattr(request, 'method', '') if request else ''), 10),
            ip_address=get_client_ip(request),
            user_agent=truncate((request.META.get('HTTP_USER_AGENT', '') if request else ''), 500),
            created_at=timezone.now(),
        )
        _bump_counters(action, user)
        return row
    except Exception as exc:                       # pragma: no cover - never break a request
        logger.warning('activity log skipped (%s): %s', action, exc)
        return None


def _bump_counters(action, user):
    """Atomic ``F() + 1`` counters on the account profile (no read-modify-write)."""
    if user is None:
        return
    from .models import UserProfile
    field = None
    if action in ('login_success', 'login_failed'):
        field = 'login_attempt_count'
    elif action == 'page_view':
        field = 'page_view_count'
    if not field:
        return
    try:
        UserProfile.objects.filter(user=user).update(**{field: F(field) + 1})
    except Exception:
        pass


def record_login_attempt(*, username_tried, user=None, request=None, user_type='',
                         successful=False, description=''):
    """Write one login attempt (success **and** failure) + bump the counter.

    Mirrors SKILL.md's ``_record_login_attempt``: on failure the account is looked
    up again from ``username_tried`` so the counter still lands on the right user.
    """
    if user is None and username_tried:
        from .services import find_user
        try:
            user = find_user(username_tried)
        except Exception:
            user = None
    action = 'login_success' if successful else 'login_failed'
    if not description:
        description = ('ورود موفق به سامانه' if successful
                       else 'تلاش ناموفق برای ورود')
    return log_activity(action, request=request, user=user, username=username_tried,
                        user_type=user_type, description=description)
