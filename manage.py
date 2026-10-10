#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def _tolerant_stdio():
    """Never crash on Persian console output (legacy Windows code pages).

    The management commands print Persian messages; if the console/redirect cannot
    encode them (e.g. `python manage.py runserver > log.txt` on a cp1252 console)
    Python would raise UnicodeEncodeError and stop the command. Replacing the
    un-encodable characters keeps everything running.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors='replace')
        except Exception:      # pragma: no cover - not a TextIOWrapper
            pass


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dana.settings')
    _tolerant_stdio()
    try:
        import django
        from django.core.management import execute_from_command_line
        from django.utils import translation
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    # v1.21 — the **console** speaks English again (owner request): with
    # LANGUAGE_CODE=fa-IR Django translates its own prompts («Email address:»
    # → «آدرس ایمیل:»), which made `createsuperuser` & friends half-Persian.
    # Only the command line is forced to English — the website and the admin
    # keep the language configured in `.env`. (setup() must run first: the
    # translation machinery needs the app registry.)
    django.setup()
    with translation.override('en'):
        execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
