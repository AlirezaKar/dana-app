""""Show what the application read from `.env` — and from where (v1.23).

    python manage.py env_check                  # the configuration of this process
    python manage.py env_check --file other.env # what that file would give
    python manage.py env_check --strict         # exit 1 on a suspicious key

The settings are read once per process, so a server (re)start is enough to pick
up an edited `.env`. This command answers the two questions that follow a
surprising value:

* **which key is in force** — every setting the app asks for, its effective
  value and whether it came from the real environment, from the file (and under
  which spelling: ``DANA_HEF_URL`` or ``HEF_URL``) or from the code default;
* **which keys are being ignored** — a line in `.env` that no setting reads is
  almost always a typo, and a key written twice (with and without the ``DANA_``
  prefix) silently lets the prefixed one win.

Values are printed as the strings the app actually sees (booleans and numbers
are converted by the settings they feed); anything named like a secret is masked.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from dana.env import PREFIX, Env

#: a value is trimmed to this many characters in the table
VALUE_WIDTH = 34
#: keys whose value must never be printed
SECRET_HINTS = ('SECRET', 'PASSWORD', 'TOKEN', 'KEY_', 'KEY')


def _mask(value: str) -> str:
    return value[:4] + '…' if len(value) > 5 else '…'


def _printable(key: str, value: str) -> str:
    if any(hint in key.upper() for hint in SECRET_HINTS):
        return _mask(value)
    return value if len(value) <= VALUE_WIDTH else value[:VALUE_WIDTH - 1] + '…'


class Command(BaseCommand):
    help = 'نمایش مقادیر خوانده‌شده از .env و اینکه هر مقدار از کجا آمده است'

    def add_arguments(self, parser):
        parser.add_argument('--file', dest='env_file', default=None,
                            help='check another .env file instead of the live configuration')
        parser.add_argument('--strict', action='store_true',
                            help='exit with an error when .env has unread or doubled keys')

    # ------------------------------------------------------------------ report
    def handle(self, *args, **options):
        live = getattr(settings, 'ENV', None)
        if live is None:                                  # pragma: no cover
            raise CommandError('The settings did not expose their .env reader.')

        path = Path(options['env_file']) if options['env_file'] else live.path
        other = bool(options['env_file'])
        if other and not path.exists():
            raise CommandError(f'{path} does not exist.')

        env = Env(path, environ=live.environ) if other else live
        if other:                                        # a fresh read of that file
            env.aliases = dict(live.aliases)

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING(f'.env → {path if path else "«none»"}'))
        if path is None or not path.exists():
            # no file is not an error: every key simply keeps the code default
            self.stdout.write(self.style.WARNING(
                '  فایل .env وجود ندارد — همهٔ مقادیر پیش‌فرض کد هستند '
                '(copy .env.sample to .env to change them).'))
        self.stdout.write(
            f'  {"keys read":<12}: {len(live.asked)}   '
            f'{"lines in file":<14}: {len(env.file)}'
            + ('   (checked with --file — the running settings are untouched)' if other else ''))

        self._table(env, live)
        suspicious = self._suspicious(env, live.used_names())
        if suspicious:
            for line in suspicious:
                self.stdout.write(self.style.WARNING('  ! ' + line))
            if options['strict']:
                raise CommandError('Suspicious .env keys — see the notes above.')
        else:
            self.stdout.write(self.style.SUCCESS(
                '  هر خط .env خوانده می‌شود و هیچ کلید تکراری نیست.'))

    @staticmethod
    def _aliases_for(live, key):
        return live.aliases.get(key[len(PREFIX):] if key.startswith(PREFIX) else key, ())

    def _table(self, env, live):
        where_labels = {'environment': 'environment', 'file': '.env file', 'default': 'default'}
        rows = []
        for key in sorted(live.asked):
            where, name, value, _default = env.describe(key, self._aliases_for(live, key))
            rows.append((key, _printable(key, value), where_labels[where], name))
        key_w = max([len('KEY')] + [len(row[0]) for row in rows])
        val_w = max([len('VALUE')] + [len(row[1]) for row in rows])
        src_w = max([len('SOURCE')] + [len(row[2]) for row in rows])
        self.stdout.write('')
        self.stdout.write(f'  {"KEY":<{key_w}}  {"VALUE":<{val_w}}  {"SOURCE":<{src_w}}  AS')
        self.stdout.write(f'  {"-" * key_w}  {"-" * val_w}  {"-" * src_w}  {"-" * 22}')
        for key, value, where, name in rows:
            self.stdout.write(f'  {key:<{key_w}}  {value:<{val_w}}  {where:<{src_w}}  {name}')
        self.stdout.write('')

    def _suspicious(self, env, used_names):
        """`.env` lines nobody reads, and keys written twice.

        ``used_names`` comes from the running settings (every accepted spelling),
        so a ``--file`` check measures that file against the same key list.
        """
        notes = []
        for name in env.file_keys():
            if name not in used_names:
                notes.append(f'{name} — هیچ تنظیمی این کلید را نمی‌خواند (غلط املایی؟)')
        for plain, prefixed in env.shadowed_file_keys():
            notes.append(f'{plain} و {prefixed} هر دو در فایل هستند — «{prefixed}» برنده است.')
        return notes
