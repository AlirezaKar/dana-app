"""Minimal ``.env`` reader — no third-party dependency.

The project keeps every tunable value in **`.env`** (a template with all keys and
their defaults is **`.env.sample`**); ``dana/settings.py`` only reads them. The
file is read **once per process**, so every server (re)start picks up whatever
`.env` says at that moment — restart the server, the new values are in force.

Precedence for every key (highest first):

1. a real environment variable ``DANA_<KEY>``   (handy one-off runs, e.g.
   ``DANA_CAR_IMAGE_MAX_GAP_SECONDS=3 python manage.py runserver``)
2. a real environment variable ``<KEY>``
3. the value inside ``.env``
4. the default passed in the code

Both spellings are accepted **in the file** as well: ``DANA_HEF_URL=…`` and
``HEF_URL=…`` mean the same thing, and ``DANA_`` wins when a line is there twice.
The code always asks for the short name (``env.get('HEF_URL')``), so an alias
(``env.int('TIMEOUT_SECONDS', aliases=('DANA_TIMEOUT_SECONDS',))``) is matched
with and without the prefix too. A real environment variable always beats the
file, alias or not.

The file format is the usual one: ``KEY=value`` per line (``export KEY=value``
also works), ``#`` starts a comment, blank lines are ignored, values may be
wrapped in single or double quotes, and an empty value (``KEY=``) means "use the
default". A ``#`` after a space at the end of an unquoted value starts a trailing
comment.

Why the two spellings exist at all: ``.env.sample`` documents every key with the
``DANA_`` prefix (``DANA_HEF_URL=http://hef.co.ir``) so the file cannot collide
with unrelated environment variables, while the code asks for the short name.
Up to v1.22 the file was searched for the **short** name only, so every prefixed
line was silently ignored and the code default won — which is why the footer
version, the logos, ``CAR_IMAGE_MAX_GAP_SECONDS``, ``HEF_URL`` and the watermark
custom text all looked "impossible to change". Both spellings work now, and
``python manage.py env_check`` prints exactly what was read, from where.
"""
from __future__ import annotations

import os
from pathlib import Path

TRUE_VALUES = {'1', 'true', 'yes', 'on', 'y', 't', 'بله'}
FALSE_VALUES = {'0', 'false', 'no', 'off', 'n', 'f', 'خیر'}

#: the prefix every key may carry in `.env` / in the real environment
PREFIX = 'DANA_'


def strip_prefix(name: str) -> str:
    """``DANA_HEF_URL`` → ``HEF_URL`` (anything else unchanged)."""
    return name[len(PREFIX):] if name.startswith(PREFIX) else name


def candidate_names(key, aliases=()) -> tuple:
    """Every name one key may be spelled with, in precedence order.

    ``candidate_names('HEF_URL')`` → ``('DANA_HEF_URL', 'HEF_URL')``: the
    ``DANA_`` spelling wins over the bare one, both in `.env` and in the real
    environment. A key that already carries the prefix — ``env.get('DANA_URL')``,
    the historical call style — also tries the doubled form, so the
    ``DANA_DANA_URL`` line `.env.sample` has always written is read as well.
    """
    names = []
    for name in (key, *aliases):
        for candidate in (PREFIX + name, name):
            if candidate and candidate not in names:
                names.append(candidate)
    return tuple(names)


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
        if line.lower().startswith('export '):     # shell-style copy/paste
            line = line[len('export '):].lstrip()
        key, _, value = line.partition('=')
        key, value = key.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        else:
            # an inline comment after an unquoted value:  KEY=10  # seconds
            if ' #' in value:
                value = value.split(' #', 1)[0].strip()
        if key:
            data[key] = value
    return data


class Env:
    """Wrapper around ``.env`` + ``os.environ`` with typed getters."""

    def __init__(self, path=None, environ=None):
        self.path = Path(path) if path else None
        self.environ = dict(os.environ if environ is None else environ)
        self.file = parse_file(path) if path else {}
        #: the keys the application asked for, spelled as the code asked for
        #: them (diagnostics: the startup line and `manage.py env_check`)
        self.asked = set()
        #: the aliases that were offered for those keys (``DANA_TIMEOUT_SECONDS``
        #: for ``SESSION_TIMEOUT_SECONDS``) — a `.env` line using one is not a typo
        self.alias_names = set()
        #: logical key → (where, name) of the value in force: 'environment',
        #: 'file' or 'default'; filled while the settings are read.
        self.sources = {}
        #: logical key → the aliases it was asked with (so the report can
        #: re-evaluate the same key against another `.env` file).
        self.aliases = {}

    # -------------------------------------------------------------- (re)reading
    def reload(self) -> dict:
        """Re-read `.env` from disk right now (the startup report does this).

        The normal path needs no reload: every process reads the file once while
        ``dana/settings.py`` is imported, so a restart is enough.
        """
        self.file = parse_file(self.path) if self.path else {}
        return self.file

    # -------------------------------------------------------------- file audit
    def file_keys(self) -> list:
        """Every key as it is written in `.env` (sorted)."""
        return sorted(self.file)

    def used_names(self) -> set:
        """Every spelling of the keys the application asks for.

        ``LOGO`` asked by the settings covers ``LOGO``, ``DANA_LOGO`` and
        ``DANA_DANA_LOGO`` — the file may use any of them.
        """
        names = set()
        for base in self.asked | self.alias_names:
            names.update({base, PREFIX + base, strip_prefix(base)})
        return names

    def unused_file_keys(self) -> list:
        """`.env` keys no setting ever asked for — almost always a typo."""
        used = self.used_names()
        return [name for name in self.file_keys() if name not in used]

    def shadowed_file_keys(self) -> list:
        """``(KEY, DANA_KEY)`` pairs in `.env`; the ``DANA_`` one wins."""
        pairs = []
        for name in self.file_keys():
            if name.startswith(PREFIX):
                continue
            if PREFIX + name in self.file:
                pairs.append((name, PREFIX + name))
        return pairs

    # ------------------------------------------------------------- raw value
    def get(self, key, default='', aliases=()):
        """String value of ``key`` (see the precedence list in the module doc)."""
        names = candidate_names(key, aliases)
        base = strip_prefix(key)
        self.asked.add(key)
        self.alias_names.update(strip_prefix(alias) for alias in aliases)
        self.aliases[base] = tuple(aliases)
        for name in names:                          # 1. + 2. real environment
            value = self.environ.get(name)
            if value not in (None, ''):
                self.sources[base] = ('environment', name)
                return value
        for name in names:                          # 3. the `.env` file
            value = self.file.get(name)
            if value not in (None, ''):
                self.sources[base] = ('file', name)
                return value
        self.sources[base] = ('default', '')               # 4. the default
        return default

    def source(self, key, aliases=()):
        """``(where, name, value)`` for ``key`` — ``where`` is ``environment``,
        ``file`` or ``default``. Diagnostics only (``manage.py env_check``)."""
        names = candidate_names(key, aliases)
        for name in names:
            value = self.environ.get(name)
            if value not in (None, ''):
                return 'environment', name, value
        for name in names:
            value = self.file.get(name)
            if value not in (None, ''):
                return 'file', name, value
        return 'default', '', ''

    def describe(self, key, aliases=()):
        """`(source, name, value, default)` — the value **and** its fallback."""
        where, name, value = self.source(key, aliases)
        if where == 'default':
            return where, '', '', self.get(key, aliases=aliases)
        return where, name, value, self.get(key, aliases=aliases)

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
