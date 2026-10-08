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
