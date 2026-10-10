"""Wizard step pages and the finish orchestration (spec.md 6.6–6.8, v1.14.1).

There is **one entry**: «کد رایانه پرونده» at the top of the upload page. The
old «اطلاعات» page and the «ورود با سایر اطلاعات» alternates are gone (owner
request: «I only enter کد رایانه»), and so is the نوع بیمه second page — the
insurance type is **detected from the found record** (the code is looked up in
both the بدنه and the شخص ثالث tables).
Finding the case creates its folder ``storage/files/<date>/<کد رایانه>-<username>/``
right away; every photo is then written into that folder as it is uploaded.

Below the finder come the three upload groups (identical for مقصر and for every
زیان‌دیده added with «اضافه کردن زیان دیده»):

1. «پشت و رو گواهینامه و کارت ماشین» — confirm (repeatable), no timer;
2. «شماره شاسی و پلاک‌ها» — timed, one-time confirm;
3. «اطراف ماشین» — timed, one-time confirm.
"""
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from app_account.activity import log_activity
from app_core.constants import INSURANCE_KEYS, INSURANCE_LABELS
from app_core.utils.digits import (national_code_error, normalize_code,
                                   normalize_national_code, to_en)
from app_core.utils.jalali import today_jalali_str
from app_media.constants import (GROUPS, GROUP_BY_ID, MULTI_PHOTO_SECTIONS,
                                 SECTION_MAX, SECTION_MIN, TITLE_BY_KEY)
from app_media.services import storage, timing

from .models import CaseSubmission, DamagedParty

MATCHED_BY_LABELS = {'file_code': 'کد رایانه پرونده'}


def _case_dict(request):
    return request.session.get('case') or None


def _auth(request):
    return request.session.get('auth') or {}


def _own_submission(request):
    case = _case_dict(request)
    if not case:
        return None
    try:
        return CaseSubmission.objects.get(pk=case['pk'])
    except CaseSubmission.DoesNotExist:
        return None


def _refresh_reference_data():
    """Re-import storage/data/*.xlsx when the files changed.

    Saving an edited Excel file is enough — no `manage.py seed_sample_data` needed.
    Costless when nothing changed (a signature check), never raises.
    """
    try:
        from app_core.startup import sync_excel_if_changed
        return sync_excel_if_changed()
    except Exception:      # never break a page because of a data problem
        return None


# --------------------------------------------------------------------------- #
# the case finder (was «مرحله ۱ — اطلاعات», now at the top of the upload page)
# --------------------------------------------------------------------------- #
def build_plate_value(p):
    """Assemble the plate component into (plate, serial) — Excel sample format."""
    def d(name):
        return to_en(p.get(name, '') or '').strip()

    letter = (p.get('plate_letter', '') or '').strip()
    d1, d2, d3, d4, d5 = d('plate_d1'), d('plate_d2'), d('plate_d3'), d('plate_d4'), d('plate_d5')
    ir1, ir2 = d('plate_ir1'), d('plate_ir2')
    plate = f'{d1}{d2}{letter}{d3}{d4}{d5}' if (d1 and d2 and letter and d3 and d4 and d5) else ''
    serial = f'{ir1}{ir2}' if (ir1 and ir2) else ''
    return plate, serial


def plate_slots(plate_value, plate_serial=''):
    slots = {'plate_d1': '', 'plate_d2': '', 'plate_letter': '', 'plate_d3': '',
             'plate_d4': '', 'plate_d5': '', 'plate_ir1': '', 'plate_ir2': ''}
    main = (plate_value or '').split('-')[0]
    if len(main) >= 6:
        slots['plate_d1'], slots['plate_d2'] = main[0], main[1]
        slots['plate_letter'] = main[2]
        slots['plate_d3'], slots['plate_d4'], slots['plate_d5'] = main[3], main[4], main[5]
    serial = (plate_serial or '').replace('-', '')
    if len(serial) >= 2:
        slots['plate_ir1'], slots['plate_ir2'] = serial[0], serial[1]
    return slots


def resolve_record(file_code, pick_id=None, branch_codes=None, insurance=None):
    """Find the case record with «کد رایانه پرونده» alone (v1.14.1).

    The insurance type is detected from the record: the code is searched in
    both the بدنه and the شخص ثالث tables (scoped to the user's شعبه‌ها). When
    the same code exists in more than one table the caller gets ``candidates``
    as ``[(insurance, record), …]`` and ``pick_id`` comes back as
    ``«body:12»`` / ``«third:7»``.

    v1.15 — the نوع بیمه chosen after login scopes the search **first**: the
    selected table wins whenever it holds the code; the other table is only a
    fallback so a code never dead-ends.
    """
    from app_records.models import MODELS, find_by_value

    if pick_id:
        ins, _, pk = str(pick_id).partition(':')
        if ins not in MODELS or not pk.isdigit():
            return None, '', 'پروندهٔ انتخاب‌شده یافت نشد.', []
        qs = MODELS[ins].objects.all()
        if branch_codes is not None:
            qs = qs.filter(branch_code__in=list(branch_codes))
        try:
            return qs.get(pk=int(pk)), ins, None, []
        except MODELS[ins].DoesNotExist:
            return None, '', 'پروندهٔ انتخاب‌شده یافت نشد.', []

    value = normalize_code(file_code or '')
    if not value:
        return None, '', 'برای یافتن پرونده، «کد رایانه پرونده» را وارد کنید.', []

    order = ('body', 'third')
    if insurance in ('body', 'third'):
        order = (insurance, 'third' if insurance == 'body' else 'body')

    matches = []
    for ins in order:
        for r in find_by_value(ins, 'file_code', value, branch_codes=branch_codes):
            matches.append((ins, r))
    if insurance in ('body', 'third'):
        scoped = [m for m in matches if m[0] == insurance]
        if scoped:
            matches = scoped
    if len(matches) == 1:
        ins, r = matches[0]
        return r, ins, None, []
    if len(matches) > 1:
        return None, '', None, matches[:10]
    return None, '', f'پرونده‌ای با کد رایانه {value} یافت نشد.', []


# --------------------------------------------------------------------------- #
# upload groups context
# --------------------------------------------------------------------------- #
def _owner_images(owner):
    if isinstance(owner, DamagedParty):
        return owner.images.all()
    return owner.images.filter(party__isnull=True)


def _group_state(owner, group):
    gid = group['id']
    if gid == 'group_docs':
        at = getattr(owner, 'docs_confirmed_at', None)
        return bool(at), False, at
    if gid == 'group_plates':
        done = bool(getattr(owner, 'plates_confirmed', False))
        return done, done, getattr(owner, 'plates_confirmed_at', None)
    done = bool(getattr(owner, 'car_confirmed', False))
    return done, done, getattr(owner, 'car_confirmed_at', None)


def groups_context(owner, gap_seconds=None):
    """The three upload groups of one party (fields + their images + confirm)."""
    from app_core.utils.digits import to_fa

    gap = to_fa(gap_seconds if gap_seconds is not None
                else timing.CAR_IMAGE_MAX_GAP_SECONDS)
    images = list(_owner_images(owner).order_by('uploaded_at'))
    out = []
    for g in GROUPS:
        confirmed, locked, confirmed_at = _group_state(owner, g)
        slots = []
        for key in g['sections']:
            imgs = [i for i in images if i.section == key]
            slots.append({
                'key': key,
                'label': TITLE_BY_KEY[key],
                'min': SECTION_MIN[key],
                'max': SECTION_MAX[key],
                'count': len(imgs),
                'images': imgs,
                # v1.17 — single-photo fields render as compact grid cells;
                # the bulk field («اطراف ماشین») keeps the wide row layout.
                'multi': key in MULTI_PHOTO_SECTIONS,
            })
        out.append({
            'id': g['id'],
            'title': g['title'],
            'hint': g['hint'].replace('{gap}', gap),
            'timed': g['timed'],
            'one_time': g['one_time_confirm'],
            'confirmed': confirmed,
            'confirmed_at': confirmed_at,
            'locked': locked,
            'slots': slots,
            'total': sum(s['count'] for s in slots),
        })
    return out


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
def _finder_context(request, submission):
    """Everything the case-finder block of the upload page needs."""
    from app_records.models import record_details

    state = {
        'file_code': (submission.entered_file_code if submission else '')
                     or (submission.any_record.computer_code if submission and submission.any_record else ''),
        'plate_changed': bool(submission.plate_changed) if submission else False,
        'has_krokki': bool(submission.has_krokki) if submission else False,
    }
    insurance = (submission.insurance_type if submission
                 else (request.session.get('login_state') or {}).get('insurance_type', ''))
    panel = {}
    if submission and submission.any_record:
        r = submission.any_record
        panel = {
            'title': f'اطلاعات پرونده {r.case_number} — کد رایانه پرونده {r.computer_code}',
            'details': record_details(insurance, r),
        }
    return {
        'finder_state': state,
        'plate_slots': plate_slots(submission.plate_value if submission else '',
                                   submission.plate_serial if submission else ''),
        'record_panel': panel,
    }


def upload_page(request):
    _refresh_reference_data()
    auth = _auth(request)
    if not auth.get('username'):
        return redirect('login')
    submission = _own_submission(request)
    insurance = (submission.insurance_type if submission else '') \
        or (request.session.get('login_state') or {}).get('insurance_type', '') \
        or (request.session.get('case') or {}).get('insurance_type', '')
    from app_core import dev_settings

    ctx = {
        'case': submission,
        'username': auth.get('username', ''),
        'insurance_type': insurance,
        'insurance_label': INSURANCE_LABELS.get(insurance, ''),
        'step': 2,
        'victims': [],
        'finder_errors': [],
        'finder_candidates': [],
        'car_max_gap': dev_settings.get(request, 'CAR_IMAGE_MAX_GAP_SECONDS'),
        'car_max_span': dev_settings.get(request, 'CAR_IMAGE_MAX_SPAN_MINUTES'),
    }
    ctx.update(_finder_context(request, submission))
    if submission:
        ctx['atfault_groups'] = groups_context(submission, ctx['car_max_gap'])
        ctx['victims'] = [{
            'obj': v,
            'groups': groups_context(v, ctx['car_max_gap']),
        } for v in submission.victims.all()]
    else:
        ctx['atfault_groups'] = []
    return render(request, 'main/upload.html', ctx)


@require_http_methods(['POST'])
def resolve_case(request):
    """«یافتن پرونده» — the only identifier is «کد رایانه پرونده» (v1.14.1)."""
    from app_records.views import user_branch_codes

    auth = _auth(request)
    if not auth.get('username'):
        return redirect('login')

    branch_codes = user_branch_codes(request)
    p = request.POST
    file_code = (p.get('file_code', '') or '').strip()
    plate_changed = p.get('plate_changed') == 'on'
    has_krokki = p.get('has_krokki') == 'on'
    plate_value, plate_serial = build_plate_value(p)

    submission = _own_submission(request)
    errors = []

    # v1.15 — the نوع بیمه picked after login scopes the lookup first
    chosen = submission.insurance_type if submission else ''
    chosen = chosen or (request.session.get('login_state') or {}).get('insurance_type', '')

    record, insurance, err, candidates = resolve_record(
        file_code, (p.get('pick_record_id', '').strip() or None), branch_codes,
        insurance=chosen or None)
    if err:
        errors.append(err)
    if not errors and plate_changed and len(plate_value) < 6:
        errors.append('شماره پلاک جدید را کامل وارد کنید (۲ رقم، حرف، ۳ رقم).')

    # changing the case while photos are already stored would orphan them
    if not errors and record and submission and submission.images.exists():
        old = submission.any_record
        if old is not None and (old.pk != record.pk
                                or submission.insurance_type != insurance):
            errors.append('برای این پرونده تصویر بارگذاری شده است؛ برای تغییر پرونده ابتدا '
                          '«شروع دوباره» بزنید.')

    if errors or candidates:
        ctx = {
            'case': submission,
            'username': auth.get('username', ''),
            'insurance_type': insurance or (submission.insurance_type if submission else ''),
            'insurance_label': INSURANCE_LABELS.get(
                insurance or (submission.insurance_type if submission else ''), ''),
            'step': 2,
            'victims': [],
            'finder_errors': errors,
            'finder_candidates': [{
                'pk': f'{ins}:{r.pk}',
                'code': r.computer_code, 'case_number': r.case_number,
                'plate': r.plate_number,
                'name': (r.driver_name if ins == 'body' else r.atfault_driver),
                'ins_label': INSURANCE_LABELS.get(ins, ''),
            } for ins, r in candidates],
            'car_max_gap': 0, 'car_max_span': 0,
            'atfault_groups': [],
        }
        fake = _finder_context(request, submission)
        fake['finder_state'].update({
            'file_code': file_code,
            'plate_changed': plate_changed,
            'has_krokki': has_krokki,
        })
        ctx.update(fake)
        return render(request, 'main/upload.html', ctx)

    # ---- create / update the submission --------------------------------- #
    if submission is None:
        # v1.17 — re-attach instead of orphaning: if this user already has an
        # UNFINISHED case for the very same record (e.g. the session expired
        # mid-flow and the photos are already in the folder), pick it up again
        # so «تصاویر نگه داشته می‌شوند» instead of starting from zero.
        candidate_qs = CaseSubmission.objects.filter(
            auth_username__iexact=auth.get('username', ''),
            finished_at__isnull=True,
        )
        if insurance == 'body' and record is not None:
            candidate_qs = candidate_qs.filter(record=record)
        elif record is not None:
            candidate_qs = candidate_qs.filter(record_third=record)
        else:
            candidate_qs = candidate_qs.filter(entered_file_code=file_code)
        submission = candidate_qs.order_by('-pk').first()
    if submission is None:
        submission = CaseSubmission()
    submission.auth_username = auth.get('username', '')
    submission.user_type = auth.get('user_type', '')
    submission.insurance_type = insurance
    submission.matched_by = 'file_code'
    if insurance == 'body':
        submission.record = record
        submission.record_third = None
    else:
        submission.record_third = record
        submission.record = None
    submission.entered_file_code = file_code
    # v1.21 — nothing else is copied out of the Excel tables: the record
    # reference (record / record_third) is the source of every other value.
    submission.plate_changed = plate_changed
    submission.plate_value = plate_value if plate_changed else ''
    submission.plate_serial = plate_serial if plate_changed else ''
    submission.has_krokki = has_krokki
    is_edit = submission.pk is not None
    if submission.finished_at is None:
        submission.save()

    # the case folder is created as soon as the case is found (owner request)
    folder = storage.ensure_case_dir(submission)

    record_label = getattr(record, 'computer_code', '') or file_code
    log_activity('case_edit' if is_edit else 'record_match', request=request,
                 description=((f'ویرایش اطلاعات پرونده {record_label}') if is_edit
                              else (f'یافتن پرونده با کد رایانه پرونده: {record_label}')),
                 object_label=record_label, method='POST')

    # the insurance type now lives on the case (auto-detected from the record)
    state = request.session.get('login_state') or {}
    state['insurance_type'] = insurance
    request.session['login_state'] = state
    request.session['case'] = {
        'pk': submission.pk,
        'user_type': submission.user_type,
        'insurance_type': insurance,
        'unique_number': submission.unique_number or '',
        'finished': bool(submission.finished_at),
        'folder': str(folder),
    }
    return redirect('step2_upload')


# --------------------------------------------------------------------------- #
# زیان‌دیده (AJAX)
# --------------------------------------------------------------------------- #
@require_http_methods(['POST'])
def add_victim(request):
    """«اضافه کردن زیان دیده» — شماره پلاک is required, the rest is optional."""
    import json

    sub = _own_submission(request)
    if not sub or sub.finished_at:
        return JsonResponse({'ok': False, 'error': 'جلسه یافت نشد.'}, status=403)

    data = json.loads(request.body.decode('utf-8') or '{}') if request.content_type \
        and 'json' in request.content_type else request.POST
    def g(key):
        return (data.get(key, '') or '').strip()

    # ---- plate: the «ایران ##» part is stored on its own (like the tables) -- #
    plate = to_en(g('plate_number'))
    plate_serial = to_en(g('plate_serial'))
    if not plate_serial and '-' in plate:      # tolerate the combined «94س225-63»
        plate, _, plate_serial = plate.partition('-')
    plate, plate_serial = plate.strip(), plate_serial.strip()
    if not plate:
        return JsonResponse({'ok': False, 'error': '«شماره پلاک» زیان‌دیده الزامی است.'}, status=400)
    if len(plate) > 32:
        return JsonResponse({'ok': False, 'error': '«شماره پلاک» معتبر نیست.'}, status=400)
    if plate_serial and not plate_serial.isdigit():
        return JsonResponse({'ok': False,
                             'error': 'بخش «ایران» شماره پلاک باید فقط عدد باشد.'}, status=400)
    if sub.victims.filter(plate_number=plate).exists():
        return JsonResponse({'ok': False,
                             'error': 'زیان‌دیده‌ای با این شماره پلاک قبلاً ثبت شده است.'},
                            status=400)

    # ---- «کد ملی»: exactly ten digits (optional, but never anything else) -- #
    national_code = normalize_national_code(g('national_code'))
    error = national_code_error(national_code)
    if error:
        return JsonResponse({'ok': False, 'error': error}, status=400)

    party = DamagedParty.objects.create(
        submission=sub,
        first_name=g('first_name'),
        last_name=g('last_name'),
        national_code=national_code,
        plate_number=plate,
        plate_serial=plate_serial,
    )
    folder = storage.ensure_dir(storage.party_dir(sub, party))
    log_activity('case_edit', request=request, method='POST',
                 description=f'افزودن زیان‌دیده {party.label}', object_label=party.label)
    from app_core import dev_settings
    from django.template.loader import render_to_string
    html = render_to_string('main/_victim_block.html', {
        'victim': party,
        'groups': groups_context(party, dev_settings.get(request, 'CAR_IMAGE_MAX_GAP_SECONDS')),
        'car_max_span': dev_settings.get(request, 'CAR_IMAGE_MAX_SPAN_MINUTES'),
    }, request=request)
    return JsonResponse({'ok': True, 'victim': {
        'id': party.pk, 'plate': party.plate_number, 'plate_serial': party.plate_serial,
        'plate_full': party.plate_full, 'label': party.label,
        'full_name': party.full_name, 'national_code': party.national_code,
        'folder': str(folder),
    }, 'html': html})


@require_http_methods(['POST'])
def remove_victim(request):
    sub = _own_submission(request)
    if not sub or sub.finished_at:
        return JsonResponse({'ok': False, 'error': 'جلسه یافت نشد.'}, status=403)
    try:
        party = sub.victims.get(pk=int(request.POST.get('id', '')))
    except (DamagedParty.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'ok': False, 'error': 'زیان‌دیده یافت نشد.'}, status=404)
    for img in party.images.all():
        storage.remove_file(img.image_path)
    import shutil
    folder = storage.party_dir(sub, party)
    label = party.label
    party.delete()
    if folder.exists():
        shutil.rmtree(folder, ignore_errors=True)
    log_activity('image_remove', request=request, method='POST',
                 description=f'حذف زیان‌دیده {label}', object_label=label)
    return JsonResponse({'ok': True})


# --------------------------------------------------------------------------- #
# finish / done / restart
# --------------------------------------------------------------------------- #
def _check_owner(request, owner, label):
    """Per-group completeness + confirmation + timing for one party.

    Returns (errors, timing_failed_group) — on a timing failure the group's
    images are discarded and its confirm is reset (same rule as the button).
    """
    errors = []
    for g in GROUPS:
        confirmed, _locked, _at = _group_state(owner, g)
        missing = []
        images = _owner_images(owner)
        for key in g['sections']:
            if images.filter(section=key).count() < SECTION_MIN[key]:
                missing.append(TITLE_BY_KEY[key])
        if missing:
            errors.append(f'{label} — بخش «{g["title"]}» ناقص است: ' + '، '.join(missing))
            continue
        if not confirmed:
            errors.append(f'{label} — بخش «{g["title"]}» هنوز تأیید نشده است.')
            continue
        if not g['timed']:
            continue
        from app_core import dev_settings
        min_total = sum(SECTION_MIN[k] for k in g['sections'])
        status, msg = timing.evaluate(
            owner, g['sections'],
            gap_seconds=dev_settings.get(request, 'CAR_IMAGE_MAX_GAP_SECONDS'),
            span_minutes=dev_settings.get(request, 'CAR_IMAGE_MAX_SPAN_MINUTES'),
            min_required=min_total,
        )
        if status in (timing.STATUS_GAP, timing.STATUS_SPAN):
            timing.discard_group(owner, g['sections'])
            if g['id'] == 'group_plates':
                owner.plates_confirmed = False
                owner.plates_confirmed_at = None
                owner.save(update_fields=['plates_confirmed', 'plates_confirmed_at'])
            else:
                owner.car_confirmed = False
                owner.car_confirmed_at = None
                owner.save(update_fields=['car_confirmed', 'car_confirmed_at'])
            errors.append(f'{label} — {msg}')
    return errors


@require_http_methods(['POST'])
def finish(request):
    submission = _own_submission(request)
    if not submission:
        return redirect('login')
    if submission.finished_at:
        return redirect('step3_done')

    errors = []
    if not submission.has_krokki:
        errors += _check_owner(request, submission, 'مقصر')
    for v in submission.victims.all():
        errors += _check_owner(request, v, f'زیان‌دیده {v.plate_number}')
    if errors:
        log_activity('finish', request=request, method='POST',
                     description='اتمام ناموفق: بخش‌های ناقص',
                     object_label='؛ '.join(e[:60] for e in errors))
        for e in errors:
            messages.error(request, e)
        return redirect('step2_upload')

    # finalize: unique number + ownership (v1.14)
    unique = storage.unique_number_for(today_jalali_str())
    auth = _auth(request)
    submission.unique_number = unique
    submission.finished_at = timezone.now()
    submission.completed_username = auth.get('username', '')
    from django.contrib.auth import get_user_model
    submission.completed_by = get_user_model().objects.filter(
        username__iexact=submission.completed_username).first()
    submission.save(update_fields=['unique_number', 'finished_at',
                                   'completed_username', 'completed_by'])

    # v1.14.1 — the watermark program runs when the upload is finalized
    # (owner request). The second, simple stamp: only «کد رایانه پرونده» as
    # v1.14.1 / v1.18 — the watermark program of the app: a transparent layer with
    # the case facts (code / case number / user / Jalali time + logos + optional
    # QR) on every photo of the case (مقصر + زیان‌دیده‌ها).
    watermarked = 0
    try:
        from app_media.services import watermark as wm
        watermarked = wm.run_simple_for_submission(
            submission, base_url=request.build_absolute_uri('/'))
    except Exception:                       # never block the finalize step
        watermarked = 0

    case = _case_dict(request)
    case['unique_number'] = unique
    case['finished'] = True
    request.session['case'] = case

    log_activity('finish', request=request, method='POST',
                 description=f'اتمام پرونده و ساخت پوشهٔ {unique}'
                             f' (واترمارک ساده روی {watermarked} تصویر)',
                 object_label=unique)
    return redirect('step3_done')


def done_page(request):
    _refresh_reference_data()
    submission = _own_submission(request)
    if not submission:
        return redirect('login')
    if not submission.finished_at:
        return redirect('step2_upload')

    from app_core import dev_settings
    dev_gap = dev_settings.get(request, 'CAR_IMAGE_MAX_GAP_SECONDS')
    ctx = {
        'case': submission,
        'step': 3,
        'car_max_span': dev_settings.get(request, 'CAR_IMAGE_MAX_SPAN_MINUTES'),
        'folder': storage.case_dir(submission),
        'folder_rel': str(storage.case_dir(submission).relative_to(storage.root())).replace('\\', '/'),
        'atfault_groups': groups_context(submission, dev_gap),
        'atfault_total': submission.images.filter(party__isnull=True).count(),
        'victims': [{'obj': v, 'groups': groups_context(v, dev_gap)}
                    for v in submission.victims.all()],
        'image_total': submission.images.count(),
        'matched_by_label': MATCHED_BY_LABELS.get(submission.matched_by, submission.matched_by),
    }
    from app_records.models import record_details
    record = submission.any_record
    ctx['record_fields'] = record_details(submission.insurance_type, record) if record else []
    return render(request, 'main/done.html', ctx)


@require_http_methods(['GET'])
def restart(request):
    log_activity('restart', request=request, description='شروع دوبارهٔ فرایند', method='GET')
    submission = _own_submission(request)
    if submission and not submission.finished_at:
        for img in list(submission.images.all()):
            storage.remove_file(img.image_path)
        storage.clean_case_dir(submission)
        submission.delete()
    request.session.pop('case', None)
    # v1.15 — a true fresh start: the نوع بیمه is chosen again (stage 2)
    request.session.pop('login_state', None)
    return redirect('login')
