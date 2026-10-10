"""Reference-data models: the imported insurance case tables.

These are the models read from the Excel files (spec.md section 5). They are
searched through during the login/authentication stage — the user proves a
case exists by matching one of its identifier fields.

v1.14 — «کد شعبه» (branch code) is a field of both insurance types. Every
record belongs to a :class:`Branch`; a login account is assigned one or more
branches (``UserProfile.branches``) and can only **see** the records of those
branches — every identifier search (کد رایانه پرونده، کد ملی، شماره پلاک، …)
is scoped that way.
"""
from django.db import models


class Branch(models.Model):
    """شعبه — the «branch id» model. Rows are created from the Excel «کد شعبه».

    v1.21 — **the name of a branch *is* its code**: the Excel column carries the
    branch name and that very value is used as the key everywhere, so ``title``
    is kept equal to ``code`` (``save()`` mirrors it) and the admin/list shows
    one value instead of two that could drift apart. Filtering still happens on
    ``branch_code`` exactly as before.
    """

    code = models.CharField('کد شعبه', max_length=32, unique=True)
    title = models.CharField('عنوان شعبه', max_length=120, blank=True,
                             help_text='همیشه همان «کد شعبه» — به‌صورت خودکار همسان می‌شود.')

    class Meta:
        verbose_name = 'شعبه'
        verbose_name_plural = 'شعبه‌ها'
        ordering = ['code']

    def save(self, *args, **kwargs):
        self.title = self.code            # name == code, by construction
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.code}'


class BaseCaseRecord(models.Model):
    """Common fields for both insurance types."""

    computer_code = models.CharField('کد رایانه پرونده', max_length=32, unique=True)
    case_number = models.CharField('شماره پرونده', max_length=32)
    branch_code = models.CharField('کد شعبه', max_length=32, blank=True, db_index=True)
    claim_reported_date = models.CharField('تاریخ اعلام خسارت', max_length=16)
    claim_reported_date_greg = models.DateField('تاریخ اعلام خسارت (میلادی)', null=True, blank=True)
    case_unit = models.CharField('واحد تشکیل پرونده', max_length=120, blank=True)
    accident_date = models.CharField('تاریخ حادثه', max_length=16, blank=True)
    accident_date_greg = models.DateField('تاریخ حادثه (میلادی)', null=True, blank=True)
    plate_number = models.CharField('شماره پلاک', max_length=16, blank=True)
    plate_serial = models.CharField('سریال پلاک', max_length=16, blank=True)
    vin = models.CharField('شماره ماشین (VIN)', max_length=64, blank=True)
    vehicle_group = models.CharField('گروه خودرو', max_length=60, blank=True)
    vehicle_model = models.CharField('سیستم خودرو', max_length=60, blank=True)
    build_year = models.CharField('سال ساخت', max_length=8, blank=True)
    accident_cause = models.CharField('علت حادثه', max_length=160, blank=True)

    class Meta:
        abstract = True
        ordering = ['-id']

    # ------------------------------------------------------------------ utils
    @property
    def full_identifier(self):
        return self.computer_code

    def get_search_value(self, field):
        return self.search_field_map().get(field) or ''

    def search_field_map(self):
        raise NotImplementedError

    def search_label(self, field):
        plate = f' — پلاک {self.plate_number}' if self.plate_number else ''
        return f'شماره پرونده {self.case_number}{plate}'

    def __str__(self):
        return f'{self.computer_code} ({self.case_number})'


class BodyInsurance(BaseCaseRecord):
    """بیمه بدنه — 17 columns of the badene Excel file."""

    policy_number = models.CharField('شماره بیمه نامه', max_length=32, blank=True)
    accident_type = models.CharField('نوع حادثه', max_length=40, blank=True)
    accident_time = models.CharField('ساعت حادثه', max_length=8, blank=True)
    driver_national_code = models.CharField('کد ملی راننده', max_length=12, blank=True)
    driver_name = models.CharField('نام راننده', max_length=120, blank=True)
    vehicle_value = models.DecimalField('ارزش خودرو (تومان)', max_digits=18, decimal_places=0, null=True, blank=True)

    class Meta(BaseCaseRecord.Meta):
        verbose_name = 'بیمه بدنه'
        verbose_name_plural = 'پرونده‌های بیمه بدنه'

    def search_field_map(self):
        return {
            'file_code': self.computer_code,
            'policy_number': self.policy_number,
            'plate_number': self.plate_number,
            'national_code': self.driver_national_code,
        }

    def search_label(self, field):
        base = super().search_label(field)
        driver = f' — {self.driver_name}' if self.driver_name else ''
        return base + driver


class ThirdPartyInsurance(BaseCaseRecord):
    """بیمه شخص ثالث مالی — 22 columns of the satheth Excel file."""

    atfault_policy_number = models.CharField('شماره بیمه نامه مقصر', max_length=32, blank=True)
    third_party_history = models.CharField('سابقه ثالث مالی', max_length=80, blank=True)
    license_type = models.CharField('نوع گواهینامه', max_length=60, blank=True)
    license_number = models.CharField('شماره گواهینامه', max_length=20, blank=True)
    license_issue_date = models.CharField('تاریخ صدور گواهینامه', max_length=16, blank=True)
    license_issue_date_greg = models.DateField('تاریخ صدور گواهینامه (میلادی)', null=True, blank=True)
    sketch_officer = models.CharField('افسر ترسیم کروکی', max_length=120, blank=True)
    report = models.CharField('گزارش', max_length=120, blank=True)
    sketch_series = models.CharField('سری کروکی', max_length=16, blank=True)
    sketch_serial = models.CharField('سریال کروکی', max_length=16, blank=True)
    atfault_driver = models.CharField('راننده مقصر', max_length=120, blank=True)
    atfault_national_code = models.CharField('کد ملی مقصر', max_length=12, blank=True)
    financial_liability = models.DecimalField('تعهد مالی (تومان)', max_digits=18, decimal_places=0, null=True, blank=True)

    class Meta(BaseCaseRecord.Meta):
        verbose_name = 'بیمه شخص ثالث مالی'
        verbose_name_plural = 'پرونده‌های بیمه شخص ثالث مالی'

    def search_field_map(self):
        return {
            'file_code': self.computer_code,
            'policy_number': self.atfault_policy_number,
            'plate_number': self.plate_number,
            'national_code': self.atfault_national_code,
        }

    def search_label(self, field):
        base = super().search_label(field)
        driver = f' — {self.atfault_driver}' if self.atfault_driver else ''
        return base + driver


MODELS = {
    'body': BodyInsurance,
    'third': ThirdPartyInsurance,
}

# Fields shown in the "اطلاعات پرونده" panel (Persian label order, display only)
DETAIL_FIELDS = {
    'body': [
        'computer_code', 'case_number', 'branch_code', 'policy_number', 'accident_date',
        'accident_type', 'accident_time', 'claim_reported_date', 'accident_cause', 'case_unit',
        'driver_national_code', 'driver_name', 'vehicle_group', 'vehicle_model',
        'plate_number', 'plate_serial', 'vin', 'build_year', 'vehicle_value',
    ],
    'third': [
        'computer_code', 'case_number', 'branch_code', 'atfault_policy_number',
        'third_party_history', 'claim_reported_date', 'case_unit', 'accident_date', 'license_type',
        'license_number', 'plate_number', 'plate_serial', 'vin', 'vehicle_group', 'vehicle_model',
        'license_issue_date', 'build_year', 'sketch_officer', 'report', 'sketch_series',
        'sketch_serial', 'atfault_driver', 'atfault_national_code', 'accident_cause',
        'financial_liability',
    ],
}


def record_details(insurance_type, record):
    """All stored values of a record, as ordered [{label, value}] for the UI."""
    from app_core.utils.digits import to_fa

    if record is None:
        return []
    fields = DETAIL_FIELDS.get(insurance_type, [])
    meta = {f.name: f for f in record._meta.get_fields() if hasattr(f, 'name')}
    out = []
    for name in fields:
        f = meta.get(name)
        if f is None:
            continue
        value = getattr(record, name, None)
        if value in (None, ''):
            continue
        if hasattr(f, 'choices') and f.choices:
            value = dict(f.choices).get(value, value)
        if isinstance(value, bool):
            value = 'بله' if value else 'خیر'
        if name in ('vehicle_value', 'financial_liability'):
            value = to_fa(f'{int(value):,}')
        else:
            value = to_fa(str(value))
        out.append({'label': getattr(f, 'verbose_name', name), 'value': value})
    return out


def _branch_filter(branch_codes):
    """``{'branch_code__in': …}`` when the account is limited to branches, else {}.

    * ``branch_codes is None``            → no restriction (admin / unassigned)
    * a (possibly empty) list of codes    → only records of **these** branches
      (a record without a «کد شعبه» is only visible to unrestricted accounts)
    """
    if branch_codes is None:
        return {}
    return {'branch_code__in': list(branch_codes)}


def search_records_scoped(insurance_type, field, q, today_only=False, limit=50,
                          branch_codes=None):
    """Search an identifier column. Returns ``(records, scope)``.

    ``branch_codes`` — the «کد شعبه» values the logged-in user may see (``None``
    = unrestricted). ``scope`` tells the caller what the list really is:

    ==========  ===============================================================
    ``query``   the user typed something — **every** record is searched, so a
                case from any earlier day is still found (istartswith)
    ``today``   empty query: the records whose claim was reported **today**
    ``recent``  empty query, but nothing was reported today (a new Jalali day,
                a weekend, a fresh database): the newest claims are shown
                instead of an empty list
    ``all``     empty query without the today limit
    ==========  ===============================================================

    The today filter is deliberately **not** applied to a typed query: it used
    to hide every case as soon as the Jalali date rolled over, which made the
    «کد رایانه پرونده» dropdown look empty both on click and while typing.
    """
    from django.db.models import F

    from app_core.utils.jalali import today_gregorian_date

    model = MODELS.get(insurance_type)
    column = {
        'body': {
            'file_code': 'computer_code',
            'policy_number': 'policy_number',
            'plate_number': 'plate_number',
            'national_code': 'driver_national_code',
            'vin': 'vin',
        },
        'third': {
            'file_code': 'computer_code',
            'policy_number': 'atfault_policy_number',
            'plate_number': 'plate_number',
            'national_code': 'atfault_national_code',
            'vin': 'vin',
        },
    }.get(insurance_type, {}).get(field)
    if not model or not column:
        return [], 'query' if q else 'all'

    qs = model.objects.exclude(**{f'{column}': ''}).filter(**_branch_filter(branch_codes))
    if q:                                   # typed → the whole table, any date
        return list(qs.filter(**{f'{column}__istartswith': q}).order_by(column)[:limit]), 'query'

    if today_only:
        rows = list(qs.filter(claim_reported_date_greg=today_gregorian_date())
                    .order_by(column)[:limit])
        if rows:
            return rows, 'today'
        # nothing today → the newest claims, so the list is never misleadingly empty
        rows = list(qs.order_by(F('claim_reported_date_greg').desc(nulls_last=True),
                                column)[:limit])
        return rows, 'recent'
    return list(qs.order_by(column)[:limit]), 'all'


def search_records(insurance_type, field, q, today_only=False, limit=50, branch_codes=None):
    """Backwards-compatible wrapper around :func:`search_records_scoped`."""
    return search_records_scoped(insurance_type, field, q, today_only=today_only,
                                 limit=limit, branch_codes=branch_codes)[0]


def find_by_value(insurance_type, field, value, branch_codes=None):
    """Exact lookup used for record details / matching (value normalized).

    ``branch_codes`` scopes the lookup to the user's شعبه‌ها exactly like
    :func:`search_records_scoped` (``None`` = unrestricted).
    """
    model = MODELS.get(insurance_type)
    column = {
        'body': {'file_code': 'computer_code', 'policy_number': 'policy_number',
                 'plate_number': 'plate_number', 'national_code': 'driver_national_code',
                 'vin': 'vin'},
        'third': {'file_code': 'computer_code', 'policy_number': 'atfault_policy_number',
                  'plate_number': 'plate_number', 'national_code': 'atfault_national_code',
                  'vin': 'vin'},
    }.get(insurance_type, {}).get(field)
    if not model or not column or not value:
        return []
    return list(model.objects.filter(**{column: value})
                .filter(**_branch_filter(branch_codes))[:10])


def sync_branches():
    """Create/update the Branch rows from the «کد شعبه» values of both tables.

    The name of a branch is its code (v1.21), so an existing row whose ``title``
    drifted away from its ``code`` is brought back in line here.
    """
    codes = set(BodyInsurance.objects.exclude(branch_code='').values_list('branch_code', flat=True))
    codes |= set(ThirdPartyInsurance.objects.exclude(branch_code='')
                 .values_list('branch_code', flat=True))
    for code in sorted(codes):
        branch, _created = Branch.objects.get_or_create(code=code)
        if branch.title != branch.code:
            branch.save(update_fields=['title'])
    # rows whose code is no longer present in either table keep their title in
    # sync too (they are still selectable for an account)
    for branch in Branch.objects.exclude(title=models.F('code')):
        branch.save(update_fields=['title'])
    return codes
