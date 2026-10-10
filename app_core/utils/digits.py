"""Digit conversion helpers (Persian / Arabic-Indic <-> ASCII)."""

FA_DIGITS = '۰۱۲۳۴۵۶۷۸۹'
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'


def to_fa(value):
    """Convert ASCII digits in a value to Persian digits (۰-۹)."""
    s = str(value)
    for i, ch in enumerate('0123456789'):
        s = s.replace(ch, FA_DIGITS[i])
    return s


def to_en(value):
    """Convert Persian / Arabic-Indic digits in a value to ASCII digits."""
    s = str(value)
    for src in (FA_DIGITS, AR_DIGITS):
        for i, ch in enumerate(src):
            s = s.replace(ch, str(i))
    return s


def normalize_code(value):
    """Normalize a user-typed code: ASCII digits, no surrounding whitespace."""
    return to_en(value or '').strip()


def clean_number(value):
    """Clean a numeric string (thousands separators, digits) to a plain integer string."""
    return (
        to_en(value or '')
        .replace(',', '')
        .replace('٬', '')
        .replace('\u200f', '')
        .strip()
    )


# --------------------------------------------------------------------------- #
# v1.21 — «کد ملی» (national code) rule
# --------------------------------------------------------------------------- #
#: a national code is exactly ten digits — nothing else
NATIONAL_CODE_LENGTH = 10
NATIONAL_CODE_ERROR = 'کد ملی باید دقیقاً ۱۰ رقم و فقط عدد باشد.'


def normalize_national_code(value):
    """Persian/Arabic digits → ASCII, dashes/spaces/ZWNJ removed."""
    s = to_en(value or '')
    for ch in ('-', ' ', '\u200c', '\u200f', '\u00a0'):
        s = s.replace(ch, '')
    return s.strip()


def national_code_error(value):
    """``''`` when the value is a valid کد ملی (or empty), else the error text.

    Rule (owner request): **exactly ten characters, all of them digits**. An
    empty value is allowed — the field stays optional.
    """
    code = normalize_national_code(value)
    if not code:
        return ''
    if len(code) != NATIONAL_CODE_LENGTH or not code.isdigit():
        return NATIONAL_CODE_ERROR
    return ''
