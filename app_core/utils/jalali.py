"""Jalali (Shamsi) date helpers built on the `jalali` package.

Convention (spec.md A2): Jalali dates from Excel are stored as Jalali strings
(e.g. "1405/06/19") for display fidelity, plus a derived Gregorian date field
used for queries such as the "today" filter.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from jalali.Jalalian import gregorian_to_jalali as _g2j

TEHRAN = ZoneInfo('Asia/Tehran')


def _jalali_serial(jy, jm, jd):
    """A strictly increasing serial for ordering Jalali dates (local use only)."""
    return jy * 400 + jm * 31 + jd


def _approx_gregorian(jy, jm, jd):
    """Rough Gregorian estimate of a Jalali date (a couple of days off at worst)."""
    anchor = date(jy + 621, 3, 21)  # Nowruz (1 Farvardin) sits around 20/21 March
    if jm <= 6:
        offset = 31 * (jm - 1) + (jd - 1)
    else:
        offset = 186 + 30 * (jm - 7) + (jd - 1)
    return anchor + timedelta(days=offset)


def jalali_to_gregorian(jy, jm, jd):
    """Jalali (y, m, d) -> Gregorian datetime.date.

    NOTE: the `jalali` package's own jalali_to_gregorian is buggy for modern
    dates (off by ~1 month). The package's gregorian_to_jalali is correct, so
    this function inverts it exactly (a few-day refinement walk).
    """
    jy, jm, jd = int(jy), int(jm), int(jd)
    target = (jy, jm, jd)
    cand = _approx_gregorian(jy, jm, jd)
    for _ in range(800):
        j = _g2j(cand.year, cand.month, cand.day)
        cur = (j.year, j.month, j.day)
        if cur == target:
            return cand
        delta = _jalali_serial(*cur) - _jalali_serial(*target)
        if delta == 0:
            raise ValueError(f'Cannot invert Jalali date {target}')
        cand -= timedelta(days=delta)
    raise ValueError(f'Cannot invert Jalali date {target}')


def today_tehran():
    """Current date in the Asia/Tehran timezone."""
    return datetime.now(TEHRAN)


def today_jalali():
    """Today as (year, month, day) in the Jalali calendar (Tehran)."""
    now = today_tehran()
    j = _g2j(now.year, now.month, now.day)
    return (j.year, j.month, j.day)


def today_jalali_str():
    """Today as a Jalali string, e.g. '1405/06/31'."""
    y, m, d = today_jalali()
    return f'{y:04d}/{m:02d}/{d:02d}'


def today_gregorian_date():
    """Today (Tehran) as a Gregorian datetime.date."""
    now = today_tehran()
    return date(now.year, now.month, now.day)


def gregorian_to_jalali_str(year, month, day):
    """(y, m, d) Gregorian -> Jalali string 'YYYY/MM/DD'."""
    j = _g2j(int(year), int(month), int(day))
    return f'{j.year:04d}/{j.month:02d}/{j.day:02d}'


def jalali_str_to_gregorian(value):
    """Jalali string ('1405/06/19', also '-'/whitespace tolerant) -> datetime.date or None."""
    if not value:
        return None
    s = to_parts(value)
    if not s:
        return None
    try:
        jy, jm, jd = (int(x) for x in s[:3])
        g = jalali_to_gregorian(jy, jm, jd)
        return date(g.year, g.month, g.day)
    except (ValueError, TypeError):
        return None


def to_parts(value):
    """Split a Jalali date string into its numeric parts; None when invalid."""
    if value is None:
        return None
    s = str(value).strip().replace('-', '/')
    parts = [p for p in s.split('/') if p != '']
    if len(parts) < 3:
        return None
    for p in parts[:3]:
        if not p.isdigit():
            return None
    return parts


def jalali_display(value):
    """Format a Gregorian date/datetime (or date-only tuple) as Jalali 'YYYY/MM/DD'."""
    if value in (None, ''):
        return None
    if isinstance(value, datetime):
        y, m, d = value.year, value.month, value.day
    elif isinstance(value, date):
        y, m, d = value.year, value.month, value.day
    else:
        return None
    return gregorian_to_jalali_str(y, m, d)
