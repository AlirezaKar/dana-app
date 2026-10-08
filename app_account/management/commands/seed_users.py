"""Create a small set of demo login accounts (idempotent).

    python manage.py seed_users

One account per user type (v1.14 — only کارشناس and نماینده are left), so the
prefix rule and the optional password can both be tried out right away:

    palireza    کارشناس   (prefix «p»)    password: 123456
    nhajir      نماینده   (prefix «n»/«د») password: 123456
"""
from django.core.management.base import BaseCommand

from app_account.services import create_login_user
from app_core.constants import USER_TYPE_LABELS

DEMO_USERS = [
    ('palireza', '123456', 'specialist', 'علی رضایی'),
    ('nhajir', '123456', 'agent', 'نمایندگی هاجر'),
]


class Command(BaseCommand):
    help = 'ساخت حساب‌های نمونه برای هر نوع کاربری (تکرارپذیر)'

    def handle(self, *args, **options):
        for username, password, user_type, name in DEMO_USERS:
            profile, created = create_login_user(
                username, password, user_type, display_name=name, is_system=True)
            state = 'ساخته شد' if created else 'موجود بود'
            pwd = 'رمز عبور: فعال' if profile.password_enabled else 'رمز عبور: غیرفعال'
            self.stdout.write(self.style.SUCCESS(
                f'{profile.username:<12} {USER_TYPE_LABELS[profile.user_type]:<16} '
                f'{pwd:<18} ({state})'))
