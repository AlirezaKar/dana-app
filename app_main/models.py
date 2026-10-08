"""CaseSubmission — one working case (login identity + entered data + images).

v1.14
-----
* the «بیمه شخص ثالث» manual identity trio (نام / کد ملی / شماره پلاک) is gone;
* every finished submission is **assigned to the user that completed it**
  (``completed_by`` / ``completed_username``) so the folders page can show only
  one's own work;
* the upload page is built from three groups of fields per party (مقصر /
  زیان‌دیده) — see ``app_media.constants.SECTION_GROUPS``:

  1. «پشت و رو گواهینامه و کارت ماشین» — confirm button, **no** timer, the
     confirm may be pressed again and again;
  2. «شماره شاسی و پلاک‌ها» — **timed** group, the confirm is one-time;
  3. «اطراف ماشین» — **timed** group, the confirm is one-time.
"""
from django.conf import settings
from django.db import models

from app_core.constants import (  # re-exported for the other apps
    INSURANCE_TYPES, MATCHED_BY, USER_TYPES,
)

__all__ = ['USER_TYPES', 'INSURANCE_TYPES', 'MATCHED_BY', 'CaseSubmission', 'DamagedParty']


class CaseSubmission(models.Model):
    unique_number = models.CharField('شماره یکتا پرونده', max_length=40, unique=True, null=True, blank=True)
    user_type = models.CharField('نوع کاربر', max_length=20, choices=USER_TYPES)
    insurance_type = models.CharField('نوع بیمه', max_length=20, choices=INSURANCE_TYPES)
    auth_username = models.CharField(
        'نام کاربری', max_length=40, blank=True,
        help_text='نام کاربری حساب سامانه (مثال: palireza) — فقط برای احراز هویت استفاده می‌شود')
    record = models.ForeignKey(
        'app_records.BodyInsurance', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='submissions')
    record_third = models.ForeignKey(
        'app_records.ThirdPartyInsurance', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='submissions')
    matched_by = models.CharField('شناسهٔ یافت‌کننده', max_length=20, choices=MATCHED_BY, blank=True)

    entered_file_code = models.CharField('کد رایانه پرونده (واردشده)', max_length=32, blank=True)
    entered_policy_number = models.CharField('شماره بیمه نامه (واردشده)', max_length=32, blank=True)
    entered_plate_number = models.CharField('شماره پلاک (واردشده)', max_length=32, blank=True)
    entered_vin = models.CharField('شماره ماشین / VIN (واردشده)', max_length=64, blank=True)
    entered_national_code = models.CharField('کد ملی (واردشده)', max_length=12, blank=True)

    plate_changed = models.BooleanField('پلاک خودرو تغییر کرده است', default=False)
    plate_value = models.CharField('پلاک جدید (کامپوننت پلاک)', max_length=32, blank=True,
                                   help_text='قالب مشابه اکسل، مثال: 94س225')
    plate_serial = models.CharField('سریال پلاک جدید', max_length=8, blank=True)

    # --- group confirmations (مقصر) ---------------------------------------- #
    #: «پشت و رو گواهینامه و کارت ماشین» — no timer, confirm may be repeated
    docs_confirmed_at = models.DateTimeField('زمان تأیید بخش اسناد', null=True, blank=True)
    #: «شماره شاسی و پلاک‌ها» — timed group, one-time confirm
    plates_confirmed = models.BooleanField('تأیید نهایی شماره شاسی و پلاک‌ها', default=False)
    plates_confirmed_at = models.DateTimeField('زمان تأیید شماره شاسی و پلاک‌ها',
                                               null=True, blank=True)
    #: «اطراف ماشین» — timed group, one-time confirm
    car_confirmed = models.BooleanField('تأیید نهایی عکس‌های اطراف ماشین', default=False)
    car_confirmed_at = models.DateTimeField('زمان تأیید نهایی اطراف ماشین', null=True, blank=True)

    # --- ownership (v1.14) -------------------------------------------------- #
    completed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='completed_cases', verbose_name='کاربر ثبت‌کننده (اتمام)')
    completed_username = models.CharField('نام کاربری ثبت‌کننده', max_length=150, blank=True)

    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)
    finished_at = models.DateTimeField('تاریخ اتمام', null=True, blank=True)

    class Meta:
        verbose_name = 'ثبت پرونده'
        verbose_name_plural = 'ثبت‌های پرونده'
        ordering = ['-id']

    # ------------------------------------------------------------------ utils
    @property
    def insurance_label(self):
        return dict(INSURANCE_TYPES).get(self.insurance_type, '')

    @property
    def user_type_label(self):
        return dict(USER_TYPES).get(self.user_type, '')

    @property
    def any_record(self):
        return self.record or self.record_third

    @property
    def record_plate(self):
        r = self.any_record
        return r.plate_number if r else ''

    @property
    def record_driver_name(self):
        r = self.any_record
        if not r:
            return ''
        return getattr(r, 'driver_name', '') or getattr(r, 'atfault_driver', '')

    def effective_plate(self):
        """Plate as stored in the Excel files (e.g. 94س225)."""
        return self.plate_value or self.record_plate

    def effective_name(self):
        r = self.any_record
        return (getattr(r, 'driver_name', '') or getattr(r, 'atfault_driver', '')) if r else ''

    def effective_national_code(self):
        r = self.any_record
        return (getattr(r, 'driver_national_code', '') or getattr(r, 'atfault_national_code', '')) if r else ''

    @property
    def computer_code(self):
        """«کد رایانه پرونده» in force — the folder name of the case."""
        return self.entered_file_code or (self.any_record.computer_code if self.any_record else '')

    def __str__(self):
        return self.unique_number or f'CaseSubmission #{self.pk}'


class DamagedParty(models.Model):
    """زیان‌دیده — one damaged party of a case (the case itself is «مقصر»).

    Added from the upload page with «اضافه کردن زیان دیده»: name fields are
    optional, **شماره پلاک is required** (it names the party's folder
    ``storage/files/<date>/<کد رایانه>-<username>/<شماره پلاک>/``). Each party
    uploads the same three image groups as مقصر and carries its own confirm
    state (the docs confirm is repeatable, the two timed ones are one-time).
    """

    submission = models.ForeignKey(
        CaseSubmission, on_delete=models.CASCADE, related_name='victims',
        verbose_name='ثبت پرونده')
    first_name = models.CharField('نام', max_length=100, blank=True)
    last_name = models.CharField('نام خانوادگی', max_length=120, blank=True)
    national_code = models.CharField('کد ملی', max_length=12, blank=True)
    plate_number = models.CharField('شماره پلاک', max_length=32)

    docs_confirmed_at = models.DateTimeField('زمان تأیید بخش اسناد', null=True, blank=True)
    plates_confirmed = models.BooleanField('تأیید نهایی شماره شاسی و پلاک‌ها', default=False)
    plates_confirmed_at = models.DateTimeField('زمان تأیید شماره شاسی و پلاک‌ها',
                                               null=True, blank=True)
    car_confirmed = models.BooleanField('تأیید نهایی عکس‌های اطراف ماشین', default=False)
    car_confirmed_at = models.DateTimeField('زمان تأیید نهایی اطراف ماشین', null=True, blank=True)

    created_at = models.DateTimeField('تاریخ ثبت', auto_now_add=True)

    class Meta:
        verbose_name = 'زیان‌دیده'
        verbose_name_plural = 'زیان‌دیدگان'
        ordering = ['id']

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def label(self):
        name = self.full_name
        return f'{name} — {self.plate_number}' if name else self.plate_number

    def __str__(self):
        return f'زیان‌دیده {self.label}'
