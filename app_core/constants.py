"""Shared domain constants (English identifiers, Persian labels).

Kept in app_core so every app (accounts, records, main, media) can import them
without creating cross-app cycles.

v1.14 — only two user types are left: **کارشناس** and **نماینده**. The login
form has no type picker any more; the user type is derived from the first
letter of the username («p» → کارشناس, «د» (also the legacy «n»/«d») →
نماینده). Any other prefix is the only validation error the login shows.
"""

USER_TYPES = [
    ('specialist', 'کارشناس'),
    ('agent', 'نماینده'),
]

INSURANCE_TYPES = [
    ('body', 'بیمه بدنه'),
    ('third', 'بیمه شخص ثالث مالی'),
]

MATCHED_BY = [
    ('file_code', 'کد رایانه پرونده'),
    ('policy_number', 'شماره بیمه نامه'),
    ('plate_number', 'شماره پلاک'),
    ('vin', 'شماره ماشین'),
    ('national_code', 'کد ملی'),
]

# Username prefix per user type — part of the **username only**:
#   کارشناس -> p… (e.g. palireza)
#   نماینده  -> د… (also accepted: the legacy latin n… / d…)
USER_TYPE_PREFIX = {
    'specialist': 'p',
    'agent': 'د',
}

#: every accepted first letter of «نماینده» usernames (Persian «د» + legacy)
AGENT_PREFIXES = ('د', 'n', 'd')
SPECIALIST_PREFIXES = ('p',)

USER_TYPE_KEYS = [k for k, _ in USER_TYPES]
INSURANCE_KEYS = [k for k, _ in INSURANCE_TYPES]
USER_TYPE_LABELS = dict(USER_TYPES)
INSURANCE_LABELS = dict(INSURANCE_TYPES)


def prefix_for(user_type):
    """Required username prefix letter for a user type ('' when there is none)."""
    return USER_TYPE_PREFIX.get(user_type, '')


def user_type_from_username(username):
    """The user type the username prefix speaks for, or ``None``.

    p… → ``'specialist'`` · د… / n… / d… → ``'agent'`` · anything else → ``None``
    (the login is refused with a single «prefix» error — no other validation).
    """
    name = (username or '').strip().lstrip('\u200c').lower()
    if not name:
        return None
    first = name[0]
    if first in SPECIALIST_PREFIXES:
        return 'specialist'
    if first in AGENT_PREFIXES:
        return 'agent'
    return None


def user_types_meta():
    """[{'key', 'label', 'prefix'}] — used by the templates / JS."""
    return [{'key': k, 'label': USER_TYPE_LABELS[k], 'prefix': prefix_for(k)}
            for k in USER_TYPE_KEYS]
