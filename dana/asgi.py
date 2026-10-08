"""ASGI config for the DANA project.

The data sync runs after Django is fully initialised (see ``dana/wsgi.py``) — never
inside ``AppConfig.ready()``, which would access the database too early.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dana.settings')

application = get_asgi_application()

# post-startup data sync (idempotent, never raises)
import sys  # noqa: E402

from app_core.startup import summary_line, sync_all  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors='replace')     # Persian output must never crash startup
    except Exception:
        pass
print(summary_line(sync_all()))
