"""Where the app lives — one answer, used by anything that leaves the app.

The watermark QR code is scanned by a phone that knows nothing about the
request that produced it, so the URL burned into the photo has to be an
**absolute** one. This helper is the only place that decides what "the app's
own address" is:

1. ``PUBLIC_BASE_URL`` from `.env` — set it on a real installation and the QR is
   correct no matter which host or proxy served the request;
2. otherwise the address the current request arrived on
   (``request.build_absolute_uri('/')``), which is right when the app is reached
   directly by its real name, and honours ``USE_X_FORWARDED_HOST`` behind a
   reverse proxy (that setting validates the header against ``ALLOWED_HOSTS``,
   so a spoofed ``Host`` cannot redirect the QR somewhere else);
3. otherwise nothing — and the caller skips the QR rather than encoding a wrong
   address.
"""
from django.conf import settings


def absolute_base_url(request=None) -> str:
    """The app's absolute base URL, without a trailing slash ('' = unknown)."""
    configured = str(getattr(settings, 'PUBLIC_BASE_URL', '') or '').strip()
    if configured:
        return configured.rstrip('/')
    if request is None:
        return ''
    try:
        return request.build_absolute_uri('/').rstrip('/')
    except Exception:
        return ''
