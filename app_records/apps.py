import logging
import os

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AppRecordsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app_records'
    verbose_name = 'پرونده‌های بیمه (app_records)'

    def ready(self):
        # NOTE: no database access here on purpose. The automatic Excel sync (and the
        # login-account sync that follows it) must run *after* Django is fully
        # initialised, otherwise Django raises:
        #   RuntimeWarning: Accessing the database during app initialization is discouraged.
        # The sync is triggered by app_core.startup.sync_all() from:
        #   * the custom `runserver` command (dev server, every start/reload)
        #   * the `sync_data` management command
        #   * dana/wsgi.py (production servers)
        # Set DANA['AUTO_SYNC_EXCEL_ON_START'] to False to switch it off.
        # NOTE: login accounts are NOT derived from these records any more — the User
        # model is independent (see app_account.models.UserProfile).
        if os.environ.get('DJANGO_DANA_SKIP_SYNC') == '1':   # pragma: no cover
            logger.info('Data auto-sync disabled by DJANGO_DANA_SKIP_SYNC=1')
