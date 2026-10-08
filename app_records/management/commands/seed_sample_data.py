"""Seed the reference data by reading the Excel files from ``storage/data/``.

Put your Excel files (e.g. ``بدنه.xlsx`` and ``شخص ثالث مالی.xlsx``) into the
``storage/data/`` folder and run:

    python manage.py seed_sample_data

Files are classified by their name (badene keywords: بدنه/badane/body;
satheth keywords: ثالث/satheth/third). Import is an upsert keyed on
کد رایانه پرونده, so re-running is safe.
"""
from django.core.management.base import BaseCommand

from app_records.importers import DATA_DIR, discover_data_files, import_file


class Command(BaseCommand):
    help = 'Read the Excel files from storage/data/ and import them into the database.'

    def add_arguments(self, parser):
        parser.add_argument('--dir', type=str, default=None,
                            help='Override the data folder (default: storage/data)')

    def handle(self, *args, **opts):
        files, unreadable = discover_data_files(opts['dir'])

        if unreadable:
            for p in unreadable:
                self.stdout.write(self.style.WARNING(
                    f'Could not classify by name — skipped: {p} '
                    '(include بدنه/badane/body or ثالث/satheth/third in the file name)'))

        if not files['body'] and not files['third']:
            self.stdout.write(self.style.WARNING(
                f'No Excel files found in {DATA_DIR}.'))
            self.stdout.write('Put the بدنه and شخص ثالث مالی Excel files in that folder, '
                              'then run this command again.')
            return

        for path in files['body']:
            ins, upd, skip = import_file(path, 'body')
            self.stdout.write(self.style.SUCCESS(
                f'بدنه: {ins} inserted, {upd} updated, {skip} skipped — {path}'))
        for path in files['third']:
            ins, upd, skip = import_file(path, 'third')
            self.stdout.write(self.style.SUCCESS(
                f'ثالث مالی: {ins} inserted, {upd} updated, {skip} skipped — {path}'))
