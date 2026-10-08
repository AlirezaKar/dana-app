"""User accounts — the single source of truth for the login (spec.md v1.5+).

The login is **completely separate from the insurance process**: it authenticates
against Django's **User** model (``django.contrib.auth``) plus this ``UserProfile``
which stores the account's **نوع کاربری** and its **شعبه‌ها**. No insurance table
is read for login — the username is a free name that only has to follow the
user-type prefix rule (v1.14 — the login form derives the type from the prefix):

  کارشناس → ``p…`` (e.g. ``palireza``) · نماینده → ``د…`` (legacy ``n…`` also)

The password is optional: an account without a usable password
(``user.set_unusable_password()``) signs in with the username alone; otherwise the
password is required and checked with Django's hashers.

v1.14 — **شعبه (branch)**: when creating a «کاربر سامانه» one or more branch ids
(``app_records.Branch``) must be selected. The account then only sees the case
records of those branches («کد شعبه») in every identifier search.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from app_core.constants import USER_TYPES
from app_core.utils.usernames import username_error


class UserProfile(models.Model):
    """Extra attributes of a login account: the user type (and a display name)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile',
        verbose_name='کاربر')
    user_type = models.CharField('نوع کاربری', max_length=20, choices=USER_TYPES)
    display_name = models.CharField('نام نمایشی', max_length=100, blank=True)
    branches = models.ManyToManyField(
        'app_records.Branch', blank=True, related_name='profiles',
        verbose_name='شعبه‌ها (کد شعبه)',
        help_text='پرونده‌هایی که این کاربر می‌بیند فقط پرونده‌های همین شعبه‌ها هستند '
                  '(بدون انتخاب = بدون محدودیت).')
    is_system = models.BooleanField('حساب نمونه', default=False,
                                    help_text='حسابی که با دستور seed_users ساخته شده است.')
    login_attempt_count = models.PositiveIntegerField('تعداد تلاش‌های ورود', default=0,
                                                      editable=False)
    page_view_count = models.PositiveIntegerField('تعداد بازدید صفحه', default=0,
                                                  editable=False)
    created_at = models.DateTimeField('تاریخ ایجاد', auto_now_add=True)

    class Meta:
        verbose_name = 'کاربر سامانه'
        verbose_name_plural = 'کاربران سامانه'

    def __str__(self):
        return f'{self.username} — {self.get_user_type_display()}'

    # ------------------------------------------------------------------ helpers
    @property
    def username(self):
        return self.user.get_username()

    @property
    def password_enabled(self):
        """False → this account signs in without a password."""
        return bool(self.user_id and self.user.has_usable_password())

    # --------------------------------------------------------------- validation
    def clean(self):
        """The username must follow the prefix rule of the user type.

        NOTE: in the admin's «add user» view the inline profile is validated *before*
        the new parent user exists (``self.user_id`` is still ``None``), so the check is
        skipped here and done by ``app_account.admin.UserProfileInlineFormSet`` — which
        sees the username typed in the parent form. Validating here without a parent
        would always fail with «نام کاربری را وارد کنید.».
        """
        super().clean()
        if not self.user_id:
            return
        err = username_error(self.user.get_username(), self.user_type)
        if err:
            raise ValidationError({'user': err})


class UserActivity(models.Model):
    """Append-only log of everything users do in the app (spec.md v1.6).

    Written by the view/middleware that owns the event (never from the admin),
    **read-only in the Django admin** (no add / change / delete), newest first.
    Anonymous visitors are logged too, with ``username_label='anonymous'``.
    """

    ACTION_CHOICES = [
        ('login_success', 'ورود موفق'),
        ('login_failed', 'ورود ناموفق'),
        ('logout', 'خروج از حساب'),
        ('page_view', 'بازدید صفحه'),
        ('insurance_select', 'انتخاب نوع بیمه'),
        ('record_match', 'یافتن پرونده'),
        ('case_edit', 'ویرایش اطلاعات پرونده'),
        ('image_upload', 'بارگذاری تصویر'),
        ('image_remove', 'حذف تصویر'),
        ('car_confirm', 'تأیید نهایی خودرو'),
        ('finish', 'اتمام و ساخت پوشه'),
        ('restart', 'شروع دوباره'),
        ('session_timeout', 'پایان خودکار نشست (۱۰ دقیقه)'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='activities',
                             verbose_name='کاربر')
    username_label = models.CharField('نام کاربری', max_length=150, blank=True,
                                      help_text='برای بازدیدکنندهٔ ناشناس: anonymous')
    user_type = models.CharField('نوع کاربری', max_length=20, choices=USER_TYPES, blank=True)
    action = models.CharField('نوع فعالیت', max_length=32, choices=ACTION_CHOICES,
                              db_index=True)
    description = models.CharField('توضیح', max_length=300, blank=True)
    object_label = models.CharField('موضوع', max_length=200, blank=True,
                                    help_text='مثلاً کد رایانه پرونده یا شمارهٔ یکتا')
    path = models.CharField('مسیر', max_length=500, blank=True)
    url_name = models.CharField('نام مسیر URL', max_length=200, blank=True)
    page_label = models.CharField('برچسب صفحه', max_length=200, blank=True)
    method = models.CharField('متد', max_length=10, blank=True)
    ip_address = models.GenericIPAddressField('آدرس IP', blank=True, null=True)
    user_agent = models.CharField('User-Agent', max_length=500, blank=True)
    created_at = models.DateTimeField('زمان', default=timezone.now, db_index=True)

    class Meta:
        verbose_name = 'فعالیت کاربر'
        verbose_name_plural = 'فعالیت‌های کاربران'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['action', '-created_at']),
            models.Index(fields=['username_label', '-created_at']),
        ]

    def __str__(self):
        who = self.username_label or (self.user.get_username() if self.user_id else 'anonymous')
        return f'{who} — {self.get_action_display()} ({self.created_at:%Y/%m/%d %H:%M})'

    # ---------------------------------------------------------------- helpers
    @property
    def is_anonymous(self):
        """True for rows written before any login (visitor_label «anonymous»)."""
        return self.user_id is None
