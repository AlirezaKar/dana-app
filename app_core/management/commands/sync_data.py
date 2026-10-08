"""Sync the reference data and/or the login accounts (one-shot).

    python manage.py sync_data

Runs after Django is fully initialised, so no RuntimeWarning and no dependency on
AppConfig.ready(). Both parts are idempotent.
"""
from django.core.management.base import BaseCommand

from app_core.startup import sync_all, sync_excel


class Command(BaseCommand):
    help = 'همگام‌سازی داده‌های اکسل و حساب‌های ورود (بدون هشدار راه‌اندازی)'

    def handle(self, *args, **options):
        result = sync_all()
        records = result.get('records')
        if records is not None:
            self.stdout.write(self.style.SUCCESS(
                f"داده‌های اکسل: {records['created']} پروندهٔ جدید، {records['updated']} به‌روزرسانی"))
