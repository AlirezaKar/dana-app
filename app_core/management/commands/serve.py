"""``serve`` — run the project on a production WSGI server.

``python manage.py runserver`` is a development tool and says so on every
start::

    WARNING: This is a development server. Do not use it in a production
    setting. Use a production WSGI or ASGI server instead.

This command is the answer to that warning: it serves the very same WSGI
application (``dana/wsgi.py``, data sync included) through **waitress** — a
pure-Python production server that also runs on Windows, so the installation
stays a single ``pip install -r requirements.txt`` away.

    python manage.py serve
    python manage.py serve --host 0.0.0.0 --port 8080 --threads 12

Host / port / thread count come from ``.env`` (``SERVER_HOST``, ``SERVER_PORT``,
``SERVER_THREADS``) and can be overridden per run. Static files are served by
WhiteNoise from ``STATIC_ROOT`` — run ``python manage.py collectstatic`` once
after a release so the admin's files are there too.
"""
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = ('Serve the project with a production WSGI server (waitress) — '
            'the supported way to run DANA outside development.')

    def add_arguments(self, parser):
        server = getattr(settings, 'SERVER', {}) or {}
        parser.add_argument('--host', default=server.get('HOST', '0.0.0.0'),
                            help='interface to bind (default: %(default)s)')
        parser.add_argument('--port', type=int, default=int(server.get('PORT', 8000)),
                            help='TCP port (default: %(default)s)')
        parser.add_argument('--threads', type=int, default=int(server.get('THREADS', 8)),
                            help='worker threads (default: %(default)s)')
        parser.add_argument('--collectstatic', action='store_true',
                            help='run `collectstatic --noinput` before serving')
        parser.add_argument('--no-checks', action='store_true',
                            help='skip the pre-flight checks (DEBUG / static files)')

    def handle(self, *args, **options):
        try:
            from waitress import serve
        except ImportError as exc:                # pragma: no cover
            raise CommandError(
                'waitress is not installed — run `pip install -r requirements.txt`.') from exc

        if options['collectstatic']:
            call_command('collectstatic', interactive=False, verbosity=0)

        if not options['no_checks']:
            self.preflight()

        # importing dana.wsgi runs the reference-data sync (never raises)
        from dana.wsgi import application

        host, port, threads = options['host'], options['port'], options['threads']
        self.stdout.write(self.style.SUCCESS(
            f'Serving DANA on http://{host}:{port}/ '
            f'(waitress, {threads} threads) — press Ctrl+C to stop.'))
        if settings.DEBUG:
            self.stdout.write(self.style.WARNING(
                'DEBUG is on: keep it off for a real installation '
                '(set DEBUG=False in .env).'))
        try:
            serve(application, host=host, port=port, threads=threads)
        except KeyboardInterrupt:
            self.stdout.write('Stopped.')

    # ------------------------------------------------------------------ checks
    def preflight(self):
        """Warn about the two things that make a deployment look broken."""
        root = getattr(settings, 'STATIC_ROOT', None)
        if root is not None and not (root / 'admin').exists():
            self.stdout.write(self.style.WARNING(
                'The Django admin files are not in STATIC_ROOT yet — run '
                '`python manage.py collectstatic` (or pass --collectstatic).'))
        if not settings.SECRET_KEY.startswith('django-insecure-'):
            return
        self.stdout.write(self.style.WARNING(
            'SECRET_KEY is still the development one — set a long random '
            'SECRET_KEY in .env before going live.'))
