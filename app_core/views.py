"""Shared views (development helpers of v1.13 + the public watermark page)."""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import dev_settings


#: the facts the QR code carries → how the page labels them
#: (short arg, long arg, label) — the short names are what the new QR codes
#: carry (every byte costs QR density); the long ones keep every photo that was
#: stamped *before* v1.22 readable, so old URLs keep opening correctly.
WM_INFO_FIELDS = (
    ('c', 'code', 'کد رایانه پرونده'),
    ('f', 'case', 'شماره پرونده'),
    ('u', 'user', 'نام کاربری'),
    ('t', 'at', 'تاریخ و ساعت'),
    ('p', 'plate', 'شماره پلاک'),
    ('i', 'policy', 'شماره بیمه نامه'),
)


@require_GET
def wm_info(request):
    """Public page behind the watermark QR code (``/wm-info/``).

    The QR stamped on every photo encodes this page's absolute URL carrying the
    case facts; scanning it shows all of them together with the two logos.
    Read-only and anonymous by design — it only ever echoes back the values the
    QR itself carried, and never touches the database.
    """
    return render(request, 'core/wm_info.html', {
        'fields': [{'label': label,
                    'value': (request.GET.get(short, '') or request.GET.get(long_, ''))
                    .strip().replace('_', ' ')}
                   for short, long_, label in WM_INFO_FIELDS],
    })


@require_POST
def dev_setting(request):
    """Change a development setting from inside the app (``/dev/setting/``).

    Body: ``key`` + ``value``. An empty ``value`` removes the override and the
    setting falls back to `.env`. Disabled entirely when ``DEV_TOOLS`` is false.
    """
    if not dev_settings.enabled():
        return JsonResponse({'ok': False, 'error': 'ابزارهای توسعه غیرفعال هستند.'}, status=403)
    key = request.POST.get('key', '')
    ok, value, error = dev_settings.set_value(request, key, request.POST.get('value', ''))
    if not ok:
        return JsonResponse({'ok': False, 'key': key, 'error': error}, status=400)
    return JsonResponse({
        'ok': True,
        'key': key,
        'value': value,
        'overridden': dev_settings.is_overridden(request, key),
    })
