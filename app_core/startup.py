"""Startup data sync — runs **after** Django is fully initialised.

The reference data (Excel) is synced from here, *never* from
``AppConfig.ready()``: at that point the app registry/database connection is not
ready yet and Django raises::

    RuntimeWarning: Accessing the database during app initialization is discouraged.

The sync is triggered by:
  * ``python manage.py runserver``  → custom command in ``app_core`` (dev)
  * ``python manage.py sync_data``  → manual one-shot
  * ``dana/wsgi.py`` / ``asgi.py``  → production servers (waitress, gunicorn, …)

All three call :func:`sync_all`, which is idempotent and never raises.

v1.23 adds a one-line **configuration report** to the same startup message: it
says how many values came from `.env`, how many from the real environment and
how many defaulted, so a restart visibly proves that `.env` was re-read.
"""
import logging

logger = logging.getLogger(__name__)


def sync_excel():
    """Re-collect the reference records from the Excel files in storage/data/."""
    from django.conf import settings
    if not (settings.DANA or {}).get('AUTO_SYNC_EXCEL_ON_START', True):
        return None
    from app_records.importers import discover_data_files, import_file

    files, unreadable = discover_data_files()
    for path in unreadable:
        logger.warning('Excel auto-sync: could not classify by name, skipped: %s', path)

    created = updated = 0
    for kind in ('body', 'third'):
        for path in files[kind]:
            ins, upd, _ = import_file(path, kind)
            created += ins
            updated += upd
            logger.info('Excel auto-sync: %s — %s (%d new, %d updated)', kind, path, ins, upd)
    return {'created': created, 'updated': updated}


def sync_all():
    """Re-collect the reference records from the Excel files. Idempotent.

    Note: the login accounts live in the User model and are **completely separate**
    — they are never derived from the records (see spec.md v1.5+). Use
    ``manage.py create_user`` / ``manage.py seed_users`` to manage them.
    """
    result = {'records': None, 'config': config_line()}
    try:
        result['records'] = sync_excel()
    except Exception as exc:              # never block startup on a data issue
        logger.warning('Excel auto-sync skipped: %s', exc)
    return result


def summary_line(result):
    """The lines the server prints on every (re)start: data sync + config.

    The configuration line is what makes "restart re-reads `.env`" visible: it
    reports how many values came from the file, the environment and the defaults,
    plus the version that is now in force.
    """
    parts = []
    records = result.get('records')
    if records is not None:
        parts.append(f"پرونده‌ها: {records['created']} جدید، {records['updated']} به‌روزرسانی")
    lines = ['همگام‌سازی داده‌ها — ' + ('؛ '.join(parts) if parts else 'غیرفعال')]
    config = result.get('config')
    if config:
        lines.append(config)
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# configuration report (v1.23) — was `.env` read, and what came out of it?
# ---------------------------------------------------------------------------
def config_counts():
    """How many effective values came from `.env` / the environment / the code.

    ``Env`` records the origin of every value while ``dana/settings.py`` is
    imported, so this is a real report, not a guess.
    """
    from django.conf import settings

    env = getattr(settings, 'ENV', None)
    counts = {'file': 0, 'environment': 0, 'default': 0}
    if env is None:
        return counts
    for key in env.asked:
        base = key[len('DANA_'):] if key.startswith('DANA_') else key
        where = (env.sources.get(base) or ('default', ''))[0]
        counts[where] = counts.get(where, 0) + 1
    return counts


def config_line():
    """One console line: where this start read its configuration from."""
    from django.conf import settings

    env = getattr(settings, 'ENV', None)
    version = getattr(settings, 'APP_VERSION', '') or getattr(settings, 'STATIC_VERSION', '')
    path = getattr(settings, 'ENV_FILE', None)
    counts = config_counts()
    if env is None or path is None or not getattr(path, 'exists', lambda: False)():
        head = 'تنظیمات: فایل .env پیدا نشد — همهٔ مقادیر پیش‌فرض کد'
    else:
        head = (f'تنظیمات: {path} خوانده شد — {counts["file"]} مقدار از فایل، '
                f'{counts["environment"]} از محیط، {counts["default"]} پیش‌فرض')
    return f'{head} — نسخه {version}'


# ---------------------------------------------------------------------------
# "changed?" based sync — used by the info pages (no manual seed_sample_data)
# ---------------------------------------------------------------------------
def data_signature(directory=None):
    """A cheap signature of the Excel files: [(name, mtime_ns, size), ...]."""
    import os

    from django.conf import settings

    folder = directory or (settings.STORAGE_ROOT / 'data')
    out = []
    try:
        for entry in sorted(os.scandir(folder), key=lambda e: e.name):
            if not entry.is_file() or entry.name.startswith('~$') or entry.name.startswith('.'):
                continue
            if not entry.name.lower().endswith(('.xlsx', '.xlsm')):
                continue
            st = entry.stat()
            # plain lists, so the JSON round-trip compares equal
            out.append([entry.name, st.st_mtime_ns, st.st_size])
    except FileNotFoundError:
        return []
    return out


def _signature_file():
    from django.conf import settings
    return settings.STORAGE_ROOT / '.excel_signature.json'


def sync_excel_if_changed(force=False, directory=None):
    """Re-import storage/data/*.xlsx when the files changed since the last run.

    Called on every GET of the info pages, so saving an edited Excel file is enough
    — no `manage.py seed_sample_data` needed. Returns a dict with the result, or
    ``None`` when nothing changed (or the sync is switched off).
    """
    import json
    import logging

    from django.conf import settings

    logger = logging.getLogger(__name__)
    if not force and not (settings.DANA or {}).get('AUTO_SYNC_ON_PAGE_VIEW', True):
        return None

    folder = directory or (settings.STORAGE_ROOT / 'data')
    signature = data_signature(folder)
    path = _signature_file()
    previous = None
    try:
        if path.exists():
            previous = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        previous = None
    if not force and previous == signature:
        return None

    result = sync_excel()
    if result is None:
        return None
    try:
        path.write_text(json.dumps(signature, ensure_ascii=False), encoding='utf-8')
    except OSError:
        pass
    logger.info('Excel re-sync on page view: %s', result)
    return result
