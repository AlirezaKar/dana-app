"""Jalali calendar template tags & filters for the DANA frontend.

Usage:
    {% load jalali_tags %}
    <span>{% jalali_year %}</span>                     -> ۱۴۰۵
    {{ some_datetime|jalali_date }}                    -> ۱۴۰۵/۰۶/۳۱
    {{ some_datetime|jalali_datetime }}                -> ۱۴۰۵/۰۶/۳۱ ۱۴:۰۵
    {{ "06/31"|to_fa }}                                -> ۰۶/۳۱
"""
from django import template
from django.utils import timezone

from app_core.utils.digits import to_fa as digits_to_fa
from app_core.utils.jalali import TEHRAN, gregorian_to_jalali_str, today_jalali

register = template.Library()


def _to_aware(value):
    if value is None:
        return None
    if timezone.is_naive(value):
        return timezone.make_aware(value, TEHRAN)
    return value


@register.simple_tag
def jalali_year():
    """Current Jalali year (Tehran) with Persian digits, e.g. ۱۴۰۵."""
    return digits_to_fa(str(today_jalali()[0]))


@register.simple_tag
def jalali_date_of(value):
    """Jalali date (Persian digits) of a Gregorian date/datetime, or '—'."""
    dt = _to_aware(value)
    if dt is None:
        return '—'
    return digits_to_fa(gregorian_to_jalali_str(dt.year, dt.month, dt.day))


@register.simple_tag
def jalali_datetime_of(value, time_sep=' '):
    """Jalali date + time (Persian digits) of a Gregorian datetime, or '—'."""
    dt = _to_aware(value)
    if dt is None:
        return '—'
    d = gregorian_to_jalali_str(dt.year, dt.month, dt.day)
    return digits_to_fa(f'{d}{time_sep}{dt.strftime("%H:%M")}')


@register.filter
def to_fa(value):
    """Persian digits for a value (0-9 -> ۰-۹)."""
    if value is None:
        return ''
    return digits_to_fa(str(value))


@register.filter
def jalali_date(value):
    return jalali_date_of(value)


@register.filter
def jalali_datetime(value):
    return jalali_datetime_of(value)
