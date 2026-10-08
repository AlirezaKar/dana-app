"""Shared views (development helpers of v1.13 + the public watermark page)."""
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from . import dev_settings


@require_GET
def wm_info(request):
    """Public page behind the watermark QR code (``/wm-info/``).

    v1.18 — the QR stamped beside the watermark texts encodes this page's URL
    carrying ``code`` / ``case`` / ``user`` / ``at``; scanning it shows those
    facts together with the two logos. Read-only and anonymous by design.
    """
    return render(request, 'core/wm_info.html', {
        'code': request.GET.get('code', ''),
        'case_number': request.GET.get('case', ''),
        'username': request.GET.get('user', ''),
        'at': request.GET.get('at', ''),
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
