"""Small request helpers used by the activity log (spec.md v1.6)."""
from django.http import HttpRequest


def get_client_ip(request):
    """Client IP, X-Forwarded-For aware. Returns ``None`` when unknown.

    Never read ``request.META['REMOTE_ADDR']`` directly — a proxy would hide the
    real client behind it.
    """
    if not isinstance(request, HttpRequest):
        return None
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '') or ''
    if forwarded:
        first = forwarded.split(',')[0].strip()
        if first:
            return first
    return request.META.get('REMOTE_ADDR') or None


def truncate(value, length):
    """Trim a raw string to a field's max_length (logs must never fail on length)."""
    if value is None:
        return ''
    text = str(value)
    return text[:length] if len(text) > length else text
