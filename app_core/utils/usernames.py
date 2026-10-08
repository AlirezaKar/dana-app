"""Username rules for the login accounts (independent of the insurance data).

v1.14 — the login form has **no user-type picker**: the type comes from the
first letter of the username itself:

* کارشناس → the username must **start with `p`** (e.g. ``palireza``, ``p.ahmadi``)
* نماینده → the username must **start with `د`** (the legacy latin ``n`` / ``d``
  prefixes are accepted too, e.g. ``nhajir``)

The rest of the username may be **anything** (latin or Persian letters, digits,
``.``, ``-``, ``_``) — it is *not* tied to a کد رایانه پرونده or any other
insurance identifier. The login itself shows **no prefix validation error**
other than «the prefix must be p or د» (owner request); the checks below are
kept for *creating* accounts (admin / management commands).
"""
import re

from app_core.constants import (
    USER_TYPE_LABELS,
    prefix_for,
    user_type_from_username,
)
from app_core.utils.digits import to_en

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 40
#: latin + Persian letters, digits, dot, dash, underscore
USERNAME_ALLOWED_RE = re.compile(r'^[a-z0-9._\-\u0600-\u06FF]+$')


def normalize_username(value):
    """Persian digits → English, lowercased, spaces/ZWNJ stripped."""
    text = to_en(value or '').strip().lower()
    return text.replace(' ', '').replace('\u200c', '')


def username_error(username, user_type):
    """Validate a username for a user type. Returns an error message or ``None``."""
    name = normalize_username(username)
    role = USER_TYPE_LABELS.get(user_type, '')
    prefix = prefix_for(user_type)

    if not name:
        return 'نام کاربری را وارد کنید.'
    if len(name) < USERNAME_MIN_LENGTH:
        return f'نام کاربری باید حداقل {USERNAME_MIN_LENGTH} کاراکتر باشد.'
    if len(name) > USERNAME_MAX_LENGTH:
        return f'نام کاربری نمی‌تواند بیشتر از {USERNAME_MAX_LENGTH} کاراکتر باشد.'
    if not USERNAME_ALLOWED_RE.match(name):
        return ('نام کاربری فقط می‌تواند شامل حروف (فارسی یا انگلیسی)، عدد، نقطه (.)، '
                'خط تیره (-) و زیرخط (_) باشد.')
    if prefix:
        if user_type_from_username(name) != user_type:
            return (f'نام کاربری برای «{role}» باید با حرف «{prefix}» شروع شود '
                    f'(مثال: {prefix}alireza).')
    elif name[0].isdigit() is False and not name[0].isalpha():
        return 'نام کاربری باید با حرف یا عدد شروع شود.'
    return None


def example_username(user_type):
    """A ready-made example username for hints (follows the prefix rule)."""
    prefix = prefix_for(user_type)
    return f'{prefix}alireza' if prefix else 'alireza'
