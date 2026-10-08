"""Minimal ``.env`` reader — no third-party dependency.

The project keeps every tunable value in **`.env`** (a template with all keys and
their defaults is **`.env.sample`**); ``dana/settings.py`` only reads them.

Precedence for every key (highest first):

1. a real environment variable ``DANA_<KEY>``   (handy one-off runs, e.g.
   ``DANA_CAR_IMAGE_MAX_GAP_SECONDS=3 python manage.py runserver``)
2. a real environment variable ``<KEY>``
3. the value inside ``.env``
4. the default passed in the code

The file format is the usual one: ``KEY=value`` per line, ``#`` starts a comment,
blank lines are ignored, values may be wrapped in single or double quotes, and an
empty value (``KEY=``) means "use the default".
"""
from __future__ import annotations

import os
from pathlib import Path

TRUE_VALUES = {'1', 'true', 'yes', 'on', 'y', 't', 'بله'}
FALSE_VALUES = {'0', 'false', 'no', 'off', 'n', 'f', 'خیر'}


def parse_file(path) -> dict:
    """Read one ``.env`` file into a plain dict (missing file → empty dict)."""
    data = {}
    p = Path(path)
    if not p.exists():
        return data
    for raw in p.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        else:
            # an inline comment after an unquoted value:  KEY=10  # seconds
            if '  #' in value:
                value = value.split('  #', 1)[0].strip()
        if key:
            data[key] = value
    return data


class Env:
    """Wrapper around ``.env`` + ``os.environ`` with typed getters."""

    def __init__(self, path=None, environ=None):
        self.path = Path(path) if path else None
        self.file = parse_file(path) if path else {}
        self.environ = dict(os.environ if environ is None else environ)

    # ------------------------------------------------------------- raw value
    def get(self, key, default='', aliases=()):
        """String value of ``key`` (see the precedence list in the module doc)."""
        for name in (f'DANA_{key}', key, *aliases):
            value = self.environ.get(name, '')
            if value != '':
                return value
        value = self.file.get(key, '')
        return value if value != '' else default

    # ------------------------------------------------------------- typed values
    def int(self, key, default=0, aliases=()):
        try:
            return int(str(self.get(key, default, aliases)).strip())
        except (TypeError, ValueError):
            return default

    def float(self, key, default=0.0, aliases=()):
        try:
            return float(str(self.get(key, default, aliases)).strip())
        except (TypeError, ValueError):
            return default

    def bool(self, key, default=False, aliases=()):
        value = str(self.get(key, '', aliases)).strip().lower()
        if value in TRUE_VALUES:
            return True
        if value in FALSE_VALUES:
            return False
        return default

    def list(self, key, default=(), aliases=()):
        """Comma-separated list (``A, B, C``); empty → the default."""
        value = str(self.get(key, '', aliases)).strip()
        if not value:
            return list(default)
        return [item.strip() for item in value.split(',') if item.strip()]

    def coords(self, key, aliases=()):
        """``35.6892,51.3890`` → ``{'lat': 35.6892, 'lng': 51.3890}``; else ``None``."""
        value = str(self.get(key, '', aliases)).strip()
        if not value:
            return None
        try:
            lat, lng = [float(part.strip()) for part in value.split(',')[:2]]
        except (TypeError, ValueError):
            return None
        return {'lat': lat, 'lng': lng}
