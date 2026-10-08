"""AJAX endpoints for the searchable dropdowns and the record-details panel.

v1.14 — every search and every record lookup is **scoped to the شعبه‌های** of
the logged-in account (``UserProfile.branches``): the dropdown only offers
«کد رایانه پرونده» / «کد ملی» / … of the same branch as the user. An account
without any assigned branch is unrestricted.
"""
from django.http import JsonResponse

from app_core.utils.digits import normalize_code

from .models import find_by_value, record_details, search_records_scoped

VALID_INSURANCE = ('body', 'third')


def _insurances(insurance):
    """v1.14.1 — an empty / «auto» insurance means «look in both tables»:
    the insurance type is detected from the found record itself."""
    return VALID_INSURANCE if insurance in ('', 'auto') else (insurance,)
VALID_FIELDS = ('file_code', 'policy_number', 'plate_number', 'national_code', 'vin')


#: shown above the dropdown list when today's claims are over (new Jalali day)
SCOPE_NOTES = {
    'recent': 'امروز پرونده‌ای با تاریخ اعلام خسارت امروز ثبت نشده است؛ '
              'آخرین پرونده‌ها نمایش داده می‌شوند. برای پرونده‌های قدیمی‌تر، کد را کامل تایپ کنید.',
    'all': '',
    'today': '',
    'query': '',
}


def user_branch_codes(request):
    """The «کد شعبه» values this account may see, or ``None`` (unrestricted).

    Comes from the app session (``session['auth']['username']``) → the
    ``User``/``UserProfile`` → ``profile.branches``. No session / no account /
    no assigned branch → ``None`` (nothing is hidden).
    """
    try:
        auth = request.session.get('auth') or {}
    except Exception:
        return None
    username = (auth.get('username') or '').strip()
    if not username:
        return None
    from django.contrib.auth import get_user_model

    user = get_user_model().objects.filter(username__iexact=username, is_active=True).first()
    if user is None:
        return None
    profile = getattr(user, 'profile', None)
    if profile is None:
        return None
    codes = list(profile.branches.values_list('code', flat=True))
    return codes or None


def search(request):
    """Type-ahead values.

    * empty ``q``  → today's claims (or the newest ones when today has none);
    * typed ``q``  → **all** records, newest first in the list, any date — so a
      case from an earlier day is still reachable by typing its code.

    Both are limited to the user's branches (v1.14).
    """
    insurance = request.GET.get('insurance', '')
    field = request.GET.get('field', '')
    q = normalize_code(request.GET.get('q', ''))
    today_only = request.GET.get('today') == '1'

    if field not in VALID_FIELDS:
        return JsonResponse({'results': [], 'scope': 'bad-request', 'note': ''})

    branch_codes = user_branch_codes(request)
    results, scopes = [], set()
    for ins in _insurances(insurance):
        records, scope = search_records_scoped(ins, field, q, today_only=today_only,
                                               branch_codes=branch_codes)
        scopes.add(scope)
        for r in records:
            value = r.get_search_value(field)
            if not value:
                continue
            results.append({'value': value, 'label': r.search_label(field)})
    # widest scope wins (all > recent > today > query) for the note
    scope = next((s for s in ('all', 'recent', 'today', 'query') if s in scopes), 'query')
    return JsonResponse({'results': results, 'scope': scope,
                         'note': SCOPE_NOTES.get(scope, '')})


def details(request):
    """All information of the record that owns the given identifier value."""
    insurance = request.GET.get('insurance', '')
    field = request.GET.get('field', 'file_code')
    value = normalize_code(request.GET.get('value', ''))

    if field not in VALID_FIELDS or not value:
        return JsonResponse({'found': False, 'details': []})

    branch_codes = user_branch_codes(request)
    for ins in _insurances(insurance):
        records = find_by_value(ins, field, value, branch_codes=branch_codes)
        if records:
            r = records[0]
            return JsonResponse({
                'found': True,
                'value': value,
                'title': f'اطلاعات پرونده {r.case_number} — کد رایانه {r.computer_code}',
                'details': record_details(ins, r),
            })
    return JsonResponse({'found': False, 'details': [], 'value': value})
