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
from app_core.utils.digits import national_code_error

__all__ = ['USER_TYPES', 'INSURANCE_TYPES', 'MATCHED_BY', 'CaseSubmission', 'DamagedParty']


def validate_national_code_field(value):
    """Model validator — «کد ملی» is exactly ten digits, nothing else (v1.21)."""
    from django.core.exceptions import ValidationError

    error = national_code_error(value)
    if error:
        raise ValidationError(error, code='national_code')


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

    # v1.21 — a ثبت پرونده keeps **references** to the Excel tables (``record``
    # / ``record_third``), never a second copy of their values: the information
    # panels read the record itself, so an updated Excel file is reflected at
    # once. The only fields stored here are the ones the user really enters —
    # «کد رایانه پرونده» (the key of the case) and, when the plate changed, the
    # new plate + its ایران serial.
    entered_file_code = models.CharField('کد رایانه پرونده (واردشده)', max_length=32, blank=True)

    plate_changed = models.BooleanField('پلاک خودرو تغییر کرده است', default=False)
    has_krokki = models.BooleanField('کروکی دارم', default=False,
                                     help_text='در صورت فعال بودن، بخش بارگذاری تصاویر مقصر نادیده گرفته می‌شود')
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

    def effective_plate_serial(self):
        """The «ایران ##» part of :meth:`effective_plate` (its own column)."""
        if self.plate_value:
            return self.plate_serial
        r = self.any_record
        return getattr(r, 'plate_serial', '') if r else ''

    @property
    def plate_slots(self):
        """The plate as the eight boxes of ``main/_plate.html`` (v1.21)."""
        from app_core.utils.plate import plate_slots
        return plate_slots(self.effective_plate(), self.effective_plate_serial())

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

    v1.21 — the plate is stored the way the insurance tables store it: the main
    part in :attr:`plate_number` (``94س225``) and the «ایران ##» part in
    :attr:`plate_serial` (``63``). «کد ملی» follows one rule: exactly ten digits.
    """

    submission = models.ForeignKey(
        CaseSubmission, on_delete=models.CASCADE, related_name='victims',
        verbose_name='ثبت پرونده')
    first_name = models.CharField('نام', max_length=100, blank=True)
    last_name = models.CharField('نام خانوادگی', max_length=120, blank=True)
    national_code = models.CharField('کد ملی', max_length=10, blank=True,
                                     validators=[validate_national_code_field],
                                     help_text='دقیقاً ۱۰ رقم (اختیاری)')
    plate_number = models.CharField('شماره پلاک', max_length=32)
    plate_serial = models.CharField('سریال پلاک (ایران ##)', max_length=8, blank=True,
                                    help_text='بخش «ایران ##» پلاک، جدا از خود پلاک')

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

    def clean(self):
        from django.core.exceptions import ValidationError

        from app_core.utils.digits import national_code_error, normalize_national_code

        self.national_code = normalize_national_code(self.national_code)
        error = national_code_error(self.national_code)
        if error:
            raise ValidationError({'national_code': error})

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    @property
    def plate_slots(self):
        """The plate as the eight boxes of ``main/_plate.html`` (v1.21)."""
        from app_core.utils.plate import plate_slots
        return plate_slots(self.plate_number, self.plate_serial)

    @property
    def plate_full(self):
        """«94س225-63» — plate + its ایران serial (the way the DB keeps them)."""
        return f'{self.plate_number}-{self.plate_serial}' if self.plate_serial else self.plate_number

    @property
    def label(self):
        name = self.full_name
        plate = self.plate_full
        return f'{name} — {plate}' if name else plate

    def __str__(self):
        return f'زیان‌دیده {self.label}'
