"""``runserver`` with the automatic data sync.

Django's ``AppConfig.ready()`` must not touch the database (it runs while the app
registry is still being initialised, which triggers
``RuntimeWarning: Accessing the database during app initialization is discouraged``).
This command runs the sync *after* ``django.setup()`` instead, right before the
development server starts — so ``python manage.py runserver`` still re-collects the
Excel reference data and the login accounts on every (re)start.
"""
import os
import sys

from django.contrib.staticfiles.management.commands.runserver import (
    Command as StaticfilesRunserverCommand,
)

from app_core.startup import sync_all, summary_line


class Command(StaticfilesRunserverCommand):
    help = 'اجرای سرور توسعه همراه با همگام‌سازی خودکار داده‌ها و حساب‌های ورود'

    def handle(self, *args, **options):
        use_reloader = options.get('use_reloader')
        in_reloader_child = os.environ.get('RUN_MAIN') == 'true'
        if not use_reloader or in_reloader_child:
            # only in the process that actually serves (not in the reloader parent)
            line = summary_line(sync_all())
            try:
                self.stdout.write(line)
            except UnicodeEncodeError:      # legacy Windows console / redirected output
                sys.stdout.write(line.encode('ascii', 'replace').decode('ascii') + '\n')
        return super().handle(*args, **options)
