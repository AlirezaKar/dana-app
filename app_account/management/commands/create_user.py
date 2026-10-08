"""Create or update one login account (any user type) with the prefix rule enforced.

    python manage.py create_user palireza 123456 --user-type specialist --name "علی رضایی"
    python manage.py create_user nreza --user-type agent          # account WITHOUT password
    python manage.py create_user nreza --set-password 123456      # enable the password later
    python manage.py create_user nreza --no-password              # disable it again

کارشناس → username must start with «p» · نماینده → «n» · other types → anything.
"""
from django.core.management.base import BaseCommand, CommandError

from app_account.services import create_login_user, set_account_password
from app_core.constants import USER_TYPE_KEYS, USER_TYPE_LABELS


class Command(BaseCommand):
    help = 'ساخت/ویرایش حساب کاربری سامانه (نام کاربری + رمز عبور اختیاری + نوع کاربری)'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('password', nargs='?', default=None,
                            help='رمز عبور؛ «-» یعنی بدون رمز عبور')
        parser.add_argument('--user-type', default='specialist', choices=USER_TYPE_KEYS)
        parser.add_argument('--name', default='')
        parser.add_argument('--no-password', action='store_true',
                            help='غیرفعال کردن رمز عبور (ورود فقط با نام کاربری)')
        parser.add_argument('--set-password', default=None, help='تنظیم/تغییر رمز عبور')
        parser.add_argument('--only-password', action='store_true',
                            help='فقط رمز عبور را تغییر بده (حساب را دست نزن)')

    def handle(self, *args, **options):
        username = options['username']
        password = options.get('set_password') or options['password']
        if password == '-':
            password = None
        if options['no_password']:
            password = None

        try:
            if options['only_password'] or options.get('set_password'):
                user = set_account_password(username, password)
                state = 'رمز عبور تنظیم شد' if user.has_usable_password() else 'رمز عبور غیرفعال شد'
                self.stdout.write(self.style.SUCCESS(f'{user.get_username()} — {state}.'))
                return
            profile, created = create_login_user(
                username, password, options['user_type'],
                display_name=options['name'], is_system=False)
        except ValueError as exc:
            raise CommandError(str(exc))

        action = 'ساخته شد' if created else 'به‌روزرسانی شد'
        pwd = 'با رمز عبور' if profile.password_enabled else 'بدون رمز عبور'
        self.stdout.write(self.style.SUCCESS(
            f'{profile.username} ({USER_TYPE_LABELS[profile.user_type]}) {action} — {pwd}.'))
