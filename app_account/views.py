"""Login + the short insurance wizard (spec.md v1.5+, v1.14).

**The login is completely separate from the insurance process.** The form has
**no user-type option cards** any more: the type comes from the first letter of
the username («p» → کارشناس, «د» — or the legacy «n»/«d» — → نماینده). The only
prefix validation is an error for any other first letter. Authentication reads
the **User** model only (Django auth user + ``UserProfile``); the insurance
record tables are never involved. The password is optional per account.

After the login the user picks the نوع بیمه (the page color follows the choice)
and lands on the upload page, where the case itself is found — the old
«شناسه‌های پرونده» page is gone.
"""
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app_core import dev_settings
from app_core.constants import (
    INSURANCE_KEYS, INSURANCE_LABELS, INSURANCE_TYPES, USER_TYPE_LABELS,
    user_type_from_username,
)
from app_core.utils.digits import to_en
from app_core.utils.usernames import normalize_username

from .activity import log_activity, record_login_attempt
from .services import authenticate_login_user, find_user


def _auth(request):
    return request.session.get('auth') or {}


def _stage(request):
    """1 = login form · 2 = نوع بیمه · 3 = straight to the upload page.

    v1.15 (owner request): the نوع بیمه page is **back** — after choosing the
    type the user goes directly to the upload page; the standalone «یافتن
    پرونده» screen is gone (the کد رایانه entry lives inside the upload page).

    v1.21 — ``?timeout=1`` is handled by :func:`login` on GET only and the URL
    is cleaned right away, so it can never swallow a POST any more.
    """
    auth = _auth(request)
    if not auth.get('username'):
        return 1
    insurance = (request.session.get('login_state') or {}).get('insurance_type')
    if request.GET.get('stage') == '2' or not insurance:
        return 2
    return 3


def _ctx(request, stage, errors=None):
    auth = _auth(request)
    insurance = (request.session.get('login_state') or {}).get('insurance_type', '')
    return {
        'stage': stage,
        'errors': errors or [],
        'auth': auth,
        'username': auth.get('username', ''),
        'user_type_label': USER_TYPE_LABELS.get(auth.get('user_type', ''), ''),
        'insurance_type': insurance,
        'insurance_label': INSURANCE_LABELS.get(insurance, ''),
        'insurance_types': INSURANCE_TYPES,
        'step': 1,
        # v1.13 — the value in force (`.env` or the tiny footer box)
        'car_max_gap': dev_settings.get(request, 'CAR_IMAGE_MAX_GAP_SECONDS'),
    }


@require_http_methods(['GET', 'POST'])
def login(request):
    # ---- «مهلت نشست» : the session ran out (browser countdown or server) ---- #
    # v1.21 — handled on **GET only** and the query string is cleaned with a
    # redirect. Before this, the flag was checked before the method, so the
    # login form (which posts to the very same URL) was answered by *this*
    # branch again: the user typed the username/password, the page simply
    # re-rendered and the login looked broken («it just reloads the page»).
    if request.method == 'GET' and request.GET.get('timeout') == '1':
        from django.contrib import messages

        from .middleware import close_session, timeout_config

        seconds, _warn, mode = timeout_config()
        already = request.session.pop('timed_out', False)
        if not already and (request.session.get('auth') or {}).get('username'):
            close_session(request, seconds=seconds, mode=mode)
        minutes = max(1, seconds // 60)
        reason = 'حضور در سامانه' if mode == 'absolute' else 'بی‌فعالیتی'
        try:
            messages.warning(
                request,
                f'مهلت نشست شما به پایان رسید ({minutes} دقیقه {reason}). '
                'برای ادامه دوباره وارد شوید.')
        except Exception:
            pass
        # a clean URL: «/» — the form action never carries «?timeout=1» again
        return redirect('login')

    if request.method == 'GET':
        stage = _stage(request)
        if stage == 3:
            return redirect('step2_upload')
        return render(request, 'account/login.html', _ctx(request, stage))

    # ------------------------------------------------------------ POST ----- #
    p = request.POST
    stage = int(p.get('stage', 0) or 0)
    errors = []

    # ---- stage 1: login (the user type comes from the username prefix) ---- #
    if stage == 1:
        username_input = p.get('username', '') or ''
        password_input = p.get('password', '') or ''

        auth = _auth(request)
        if auth and not username_input:
            # already signed in — just continue (GET routes by stage)
            return redirect('login')

        profile, username, err = authenticate_login_user(username_input, password_input)
        if err:
            errors.append(err)
            # every failed attempt is logged (with the username that was tried)
            record_login_attempt(username_tried=username_input or username,
                                 user=None, request=request,
                                 user_type=user_type_from_username(username) or '',
                                 successful=False, description=f'تلاش ناموفق: {err}')
        else:
            request.session['auth'] = {
                'username': username,
                # v1.14 — the type the prefix speaks for (no picker on the form)
                'user_type': user_type_from_username(username) or profile.user_type,
                'display_name': profile.display_name,
                'password_enabled': profile.password_enabled,
                'at': timezone.now().isoformat(),
            }
            request.session.pop('case', None)
            request.session['login_state'] = {}
            record_login_attempt(username_tried=username, user=profile.user,
                                 request=request, user_type=profile.user_type,
                                 successful=True,
                                 description=f'ورود موفق ({profile.get_user_type_display()})')
            return redirect('login')

    # ---- stage 2: insurance type (v1.15 — the page is back) --------------- #
    elif stage == 2:
        auth = _auth(request)
        if not auth:
            return redirect('login')
        insurance = p.get('insurance_type', '')
        if insurance not in INSURANCE_KEYS:
            errors.append('برای ادامه، نوع بیمه را انتخاب کنید.')
        else:
            state = request.session.get('login_state') or {}
            state['insurance_type'] = insurance
            request.session['login_state'] = state
            log_activity('insurance_select', request=request,
                         description=f'انتخاب {INSURANCE_LABELS.get(insurance, insurance)}',
                         object_label=INSURANCE_LABELS.get(insurance, insurance),
                         method='POST')
            # v1.15 — after choosing the type: straight to the upload page
            return redirect('step2_upload')

    return render(request, 'account/login.html', _ctx(request, stage, errors))


def logout(request):
    """End the login session (the insurance process is separate and starts again)."""
    log_activity('logout', request=request, description='خروج از حساب', method='GET')
    for key in ('auth', 'login_state', 'case'):
        request.session.pop(key, None)
    return redirect('login')


@require_http_methods(['GET'])
def session_ping(request):
    """Keep the session alive (the «ادامهٔ کار» button) — v1.12.

    The request itself refreshes ``auth['last_seen']`` in
    ``SessionTimeoutMiddleware``; the answer tells the page how much time is
    left so its countdown matches the server.
    """
    from .middleware import session_remaining, timeout_config

    seconds, warn, mode = timeout_config()
    remaining = session_remaining(request)
    return JsonResponse({
        'ok': remaining > 0,
        'seconds': seconds,
        'warn': warn,
        'remaining': remaining,
        'mode': mode,
        'timeout_url': '/?timeout=1',
    })


@require_http_methods(['GET'])
def check_user(request):
    """Does this account exist, and does it need a password?

    Used by the login page to hide the password field for accounts that sign in
    with the username alone. Returns no password data — only the flag. The user
    type itself is derived from the username prefix (v1.14) and echoed back for
    the live hint next to the form.
    """
    username = request.GET.get('username', '')
    name = normalize_username(username)
    detected = user_type_from_username(name)
    user = find_user(name) if name else None
    profile = getattr(user, 'profile', None) if user is not None else None
    return JsonResponse({
        'valid': bool(name),
        'prefix_ok': bool(detected),
        'user_type': detected or '',
        'user_type_label': USER_TYPE_LABELS.get(detected, '') if detected else '',
        'exists': user is not None,
        'needs_password': bool(user is not None and user.has_usable_password()),
        'display_name': (profile.display_name if profile else '') or '',
    })
