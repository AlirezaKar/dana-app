"""Import the reference data from the Excel files.

Explicit files:
    python manage.py import_records --badane data/badane.xlsx --satheth data/satheth.xlsx

Or let it auto-discover everything in storage/data/:
    python manage.py import_records
"""
from django.core.management.base import BaseCommand

from app_records import importers


class Command(BaseCommand):
    help = 'Import insurance case reference data from Excel files into the database.'

    def add_arguments(self, parser):
        parser.add_argument('--badane', type=str, help='Path to the بیمه بدنه Excel file (.xlsx)')
        parser.add_argument('--satheth', type=str, help='Path to the بیمه شخص ثالث مالی Excel file (.xlsx)')
        parser.add_argument('--dir', type=str, default=None,
                            help='Auto-discover Excel files in this folder (default: storage/data)')

    def handle(self, *args, **opts):
        files, unreadable = {}, []
        if not opts['badane'] and not opts['satheth']:
            files, unreadable = importers.discover_data_files(opts['dir'])
            for p in unreadable:
                self.stdout.write(self.style.WARNING(f'Could not classify by name — skipped: {p}'))
            if not files['body'] and not files['third']:
                self.stdout.write(self.style.WARNING(
                    'No input file given and nothing found in storage/data/ — nothing to do.'))
                return
        else:
            files['body'] = [opts['badane']] if opts['badane'] else []
            files['third'] = [opts['satheth']] if opts['satheth'] else []

        for path in files['body']:
            ins, upd, skip = importers.import_file(path, 'body')
            self.stdout.write(self.style.SUCCESS(
                f'بدنه: {ins} row inserted, {upd} updated, {skip} skipped ({path})'))
        for path in files['third']:
            ins, upd, skip = importers.import_file(path, 'third')
            self.stdout.write(self.style.SUCCESS(
                f'ثالث مالی: {ins} row inserted, {upd} updated, {skip} skipped ({path})'))
