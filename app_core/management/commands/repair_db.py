"""Bring an old ``db.sqlite3`` up to the current models — v1.12.

The project is often copied around (a laptop, the server, a demo machine) together
with its ``db.sqlite3``. When the database is older than the code, a page dies with
``no such column: app_media_caseimage.saved_name``. ``manage.py migrate`` only helps
when the migration is still *pending*: if ``django_migrations`` already lists it
(the file was copied after a migration was recorded but before it was applied, or
SQLite's journal was not flushed before the copy ``-wal``), ``migrate`` answers
"No migrations to apply" and the column stays missing.

This command looks at the real schema instead of the migration table: for every
model it compares the table columns with the fields and adds what is missing —
exactly the fix for "no such column" — and tells you what it did.
"""
from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Add columns that the models expect but the database is missing (fixes "no such column").'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='only report what would be added')

    def handle(self, *args, **options):
        dry = options['dry_run']
        existing_tables = set(connection.introspection.table_names())
        added, skipped, pending = [], [], []

        for model in apps.get_models():
            table = model._meta.db_table
            if table not in existing_tables:
                pending.append(f'{table} (کل جدول نیست — migrate لازم است)')
                continue
            with connection.cursor() as cur:
                cur.execute(f'PRAGMA table_info({table})') if connection.vendor == 'sqlite' \
                    else cur.execute(
                        'SELECT column_name FROM information_schema.columns WHERE table_name = %s', [table])
                have = {row[1] if connection.vendor == 'sqlite' else row[0] for row in cur.fetchall()}

            for field in model._meta.local_fields:
                column = field.column
                if column in have or not field.concrete:
                    continue
                db_type = field.db_type(connection)
                if db_type is None:                     # reverse relations etc.
                    continue
                sql = f'ALTER TABLE {table} ADD COLUMN {column} {db_type}'
                if not field.null:
                    default = field.get_default()
                    if default is None:
                        skipped.append(f'{table}.{column} (NOT NULL بدون مقدار پیش‌فرض — دستی)')
                        continue
                    if isinstance(default, bool):
                        sql += f' DEFAULT {int(default)} NOT NULL'
                    elif isinstance(default, (int, float)):
                        sql += f' DEFAULT {default} NOT NULL'
                    else:
                        # '' for the char fields — an old row simply has no value yet
                        sql += " DEFAULT '" + str(default).replace("'", "''") + "' NOT NULL"
                if dry:
                    added.append(f'{table}.{column} {db_type}  (dry-run)')
                    continue
                with connection.cursor() as cur:
                    cur.execute(sql)
                added.append(f'{table}.{column} {db_type}')

        self.stdout.write('')
        for line in added:
            self.stdout.write(self.style.SUCCESS(f'  + added   {line}'))
        for line in skipped:
            self.stdout.write(self.style.WARNING(f'  ! skipped {line}'))
        for line in pending:
            self.stdout.write(self.style.WARNING(f'  ! {line}'))
        if not (added or skipped or pending):
            self.stdout.write(self.style.SUCCESS('  همهٔ ستون‌ها موجود هستند — چیزی برای تعمیر نیست.'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n{len(added)} ستون اضافه شد.'))
            if pending:
                self.stdout.write('برای جدول‌های ناقص «python manage.py migrate» را اجرا کنید.')
