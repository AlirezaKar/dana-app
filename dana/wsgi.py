"""WSGI config for the DANA project.

The data sync (Excel reference data + login accounts) runs here — after Django is
fully initialised — so production servers (waitress, gunicorn, …) also start with
up-to-date data. It is deliberately **not** in ``AppConfig.ready()``, which would
query the database during app initialization and raise::

    RuntimeWarning: Accessing the database during app initialization is discouraged.
"""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dana.settings')

application = get_wsgi_application()

# post-startup data sync (idempotent, never raises)
import sys  # noqa: E402

from app_core.startup import summary_line, sync_all  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(errors='replace')     # Persian output must never crash startup
    except Exception:
        pass
print(summary_line(sync_all()))
