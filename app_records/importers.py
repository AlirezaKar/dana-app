"""Excel import for the two reference-data models (spec.md 6.4).

Header mapping is based on the Persian column headers of the Excel files.
Jalali dates are kept as Jalali strings and a Gregorian date is derived for
queries (the "today" filter). Upsert is keyed on ``computer_code``.
"""
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from app_core.utils.digits import clean_number, to_en
from app_core.utils.jalali import jalali_str_to_gregorian

DATE_RE = re.compile(r'^\d{4}/\d{1,2}/\d{1,2}$')


def _norm_header(h):
    """Normalize an Excel header for matching (digits, yeh/ke variants, spaces,
    tatweel/ZWNJ/ZWSP — the real files contain 'تاریـخ' with tatweel)."""
    s = to_en(str(h or '')).strip()
    s = s.replace('ي', 'ی').replace('ك', 'ک')
    for ch in ('ـ', '\u200c', '\u200b', '\u00a0', '\u200f'):
        s = s.replace(ch, '')
    s = re.sub(r'\s+', ' ', s)
    return s


BODY_HEADER_MAP = {
    'کد رایانه پرونده': 'computer_code',
    'شماره پرونده': 'case_number',
    'کد شعبه': 'branch_code',
    'شعبه': 'branch_code',
    'شماره بیمه نامه': 'policy_number',
    'تاریخ حادثه': 'accident_date',
    'نوع حادثه': 'accident_type',
    'ساعت حادثه': 'accident_time',
    'تاریخ اعلام خسارت': 'claim_reported_date',
    'علت حادثه': 'accident_cause',
    'واحد تشکیل پرونده': 'case_unit',
    'کد ملی راننده': 'driver_national_code',
    'نام راننده': 'driver_name',
    'گروه خودرو': 'vehicle_group',
    'سیستم خودرو': 'vehicle_model',
    'شماره پلاک': 'plate_number',
    'سریال پلاک': 'plate_serial',
    'شماره ماشین': 'vin',
    'شماره شاسی': 'vin',
    'شاسی': 'vin',
    'vin': 'vin',
    'سال ساخت': 'build_year',
    'ارزش خودرو': 'vehicle_value',
}

SATHEH_HEADER_MAP = {
    'کد پرونده': 'computer_code',
    'کد رایانه پرونده': 'computer_code',
    'شماره پرونده': 'case_number',
    'کد شعبه': 'branch_code',
    'شعبه': 'branch_code',
    'شماره بیمه نامه مقصر': 'atfault_policy_number',
    'شماره بیمه نامه': 'atfault_policy_number',
    'سابقه ثالث مالی': 'third_party_history',
    'تاریخ اعلام خسارت': 'claim_reported_date',
    'واحد تشکیل پرونده': 'case_unit',
    'تاریخ حادثه': 'accident_date',
    'نوع گواهینامه': 'license_type',
    'شماره گواهینامه': 'license_number',
    'شماره پلاک': 'plate_number',
    'سریال پلاک': 'plate_serial',
    'شماره ماشین': 'vin',
    'شماره شاسی': 'vin',
    'شاسی': 'vin',
    'vin': 'vin',
    'گروه خودرو': 'vehicle_group',
    'سیستم خودرو': 'vehicle_model',
    'تاریخ صدور گواهینامه': 'license_issue_date',
    'سال ساخت': 'build_year',
    'افسر ترسیم کروکی': 'sketch_officer',
    'گزارش': 'report',
    'سری کروکی': 'sketch_series',
    'سریال کروکی': 'sketch_serial',
    'راننده مقصر': 'atfault_driver',
    'کد ملی مقصر': 'atfault_national_code',
    'علت حادثه': 'accident_cause',
    'تعهد مالی': 'financial_liability',
}

JALALI_DATE_FIELDS = {
    'accident_date': 'accident_date_greg',
    'claim_reported_date': 'claim_reported_date_greg',
    'license_issue_date': 'license_issue_date_greg',
}
MONEY_FIELDS = {'vehicle_value', 'financial_liability'}
CODE_FIELDS = {
    'computer_code', 'case_number', 'branch_code', 'policy_number', 'atfault_policy_number',
    'driver_national_code', 'atfault_national_code', 'license_number',
    'plate_serial', 'sketch_series', 'sketch_serial', 'build_year', 'vin',
}


def _clean_value(field, raw):
    if raw is None:
        return ''
    s = str(raw).strip()
    if not s:
        return ''
    if field in MONEY_FIELDS:
        s2 = clean_number(s)
        if not s2:
            return None
        try:
            return Decimal(s2)
        except InvalidOperation:
            return None
    if field in JALALI_DATE_FIELDS:
        s = to_en(s)
        m = DATE_RE.match(s)
        if not m:
            return s  # keep as-is when unparseable; greg stays null
        parts = s.split('/')
        return f'{int(parts[0]):04d}/{int(parts[1]):02d}/{int(parts[2]):02d}'
    if field in CODE_FIELDS:
        return to_en(s).strip()
    if field == 'accident_time':
        return to_en(s)
    return s


def _attach_greg(fields, data):
    for jfield, gfield in JALALI_DATE_FIELDS.items():
        if jfield in data and data.get(jfield):
            data[gfield] = jalali_str_to_gregorian(data[jfield])


def rows_to_records(kind, rows):
    """Convert raw excel rows (list of dicts header->value) into model field dicts."""
    header_map = BODY_HEADER_MAP if kind == 'body' else SATHEH_HEADER_MAP
    out = []
    for row in rows:
        norm = {}
        for header, value in row.items():
            nh = _norm_header(header)
            if nh in header_map:
                norm[header_map[nh]] = value
        data = {f: _clean_value(f, v) for f, v in norm.items()}
        _attach_greg(fields=None, data=data)
        if data.get('computer_code'):
            out.append(data)
    return out


def read_workbook(path, kind):
    """Read an .xlsx file into a list of {header: value} row dicts.

    Layout-tolerant: the header row is auto-detected within the first 10 rows
    (real files have a merged title row above the green header row and the
    sheet is right-to-left), then rows are matched by header name — column
    position and styling are irrelevant.
    """
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    all_rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    if not all_rows:
        return []
    header_map = BODY_HEADER_MAP if kind == 'body' else SATHEH_HEADER_MAP
    known = {_norm_header(h) for h in header_map}

    header_idx, best = 0, 0
    for i, row in enumerate(all_rows[:10]):
        matches = sum(1 for cell in row if cell is not None and _norm_header(cell) in known)
        if matches > best:
            best, header_idx = matches, i

    headers = [str(h) if h is not None else '' for h in all_rows[header_idx]]
    rows = []
    for values in all_rows[header_idx + 1:]:
        row = {}
        for h, v in zip(headers, values):
            if h:
                row[h] = v
        if any(v not in (None, '') for v in row.values()):
            rows.append(row)
    return rows


def import_file(path, kind):
    """Import one Excel file. Returns (inserted, updated, skipped)."""
    from .models import MODELS
    model = MODELS[kind]
    rows = read_workbook(path, kind)
    records = rows_to_records(kind, rows)
    inserted = updated = skipped = 0
    for data in records:
        code = data.get('computer_code')
        if not code:
            skipped += 1
            continue
        data = {k: v for k, v in data.items() if v not in (None, '') or k in JALALI_DATE_FIELDS.values()}
        obj, created = model.objects.update_or_create(computer_code=code, defaults=data)
        if created:
            inserted += 1
        else:
            updated += 1
    # v1.14 — every «کد شعبه» becomes a Branch (the user-assignment model)
    try:
        from .models import sync_branches
        sync_branches()
    except Exception:
        pass
    return inserted, updated, skipped


# ---------------------------------------------------------------------------
# storage/data auto-discovery
# ---------------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / 'storage' / 'data'

BADENE_KEYWORDS = ('بدنه', 'badane', 'badene', 'body')
SATHEH_KEYWORDS = ('ثالث', 'satheth', 'sath', 'third')


def classify_filename(name):
    """Return 'body' / 'third' / None based on the Excel file name."""
    n = to_en(str(name)).lower()
    if any(k in n for k in BADENE_KEYWORDS):
        return 'body'
    if any(k in n for k in SATHEH_KEYWORDS):
        return 'third'
    return None


def discover_data_files(directory=None):
    """Scan the storage/data folder for Excel files.

    Returns ({'body': [paths], 'third': [paths]}, [unreadable paths]).
    """
    directory = Path(directory) if directory else DATA_DIR
    result = {'body': [], 'third': []}
    unreadable = []
    if not directory.exists():
        return result, unreadable
    for p in sorted(directory.iterdir()):
        if not p.is_file() or p.suffix.lower() not in ('.xlsx', '.xlsm'):
            continue
        kind = classify_filename(p.name)
        if kind is None:
            unreadable.append(str(p))
        else:
            result[kind].append(str(p))
    return result, unreadable
