"""Image endpoints: immediate upload, remove, group confirm, secure serving.

v1.14 — photos are stored straight into their final folder
(``storage/files/<date>/<کد رایانه>-<username>/[<شماره پلاک>/]<field>.jpg``),
named after the field they were taken for. There is no GPS any more. The
confirm endpoint handles the three upload groups:

* «پشت و رو گواهینامه و کارت ماشین» — repeatable confirm, no timer;
* «شماره شاسی و پلاک‌ها» and «اطراف ماشین» — one-time confirm with the
  timing rule (the same seconds in every part).
"""
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from PIL import Image as PILImage

from app_account.activity import log_activity

from .constants import (GROUP_BY_ID, GROUPS, SECTION_KEYS, SECTION_MIN,
                        SECTION_TO_GROUP, TITLE_BY_KEY)
from .models import CaseImage
from .services import storage, timing

#: v1.16 — an explicit image-type map: ``mimetypes`` relies on the OS registry
#: (missing on some Windows installs) and an octet-stream response makes the
#: browser download the file instead of displaying it.
_IMAGE_TYPES = {
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.jfif': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.tif': 'image/tiff',
    '.tiff': 'image/tiff',
}


def _own_submission(request):
    case = request.session.get('case')
    if not case:
        return None
    from app_main.models import CaseSubmission
    try:
        return CaseSubmission.objects.get(pk=case['pk'])
    except CaseSubmission.DoesNotExist:
        return None


def _own_party(request, sub, raw):
    """The زیان‌دیده of ``raw`` (or ``None`` for مقصر) — only inside this case."""
    raw = (raw or '').strip()
    if not raw:
        return None
    from app_main.models import DamagedParty
    try:
        party = DamagedParty.objects.get(pk=int(raw))
    except (DamagedParty.DoesNotExist, ValueError, TypeError):
        return None
    return party if party.submission_id == sub.pk else 'invalid'


def _get_owned_image(request, image_id):
    sub = _own_submission(request)
    if not sub:
        return None
    try:
        img = CaseImage.objects.get(pk=image_id)
    except CaseImage.DoesNotExist:
        return None
    return img if img.submission_id == sub.pk else None


def _owner(sub, party):
    return party if party is not None else sub


def _group_state(owner, group):
    """(confirmed, locked) — a one-time confirm locks its group for good."""
    gid = group['id']
    if gid == 'group_docs':
        return getattr(owner, 'docs_confirmed_at', None) is not None, False
    if gid == 'group_plates':
        return getattr(owner, 'plates_confirmed', False), getattr(owner, 'plates_confirmed', False)
    return getattr(owner, 'car_confirmed', False), getattr(owner, 'car_confirmed', False)


@csrf_exempt
@require_http_methods(['POST'])
def upload(request):
    """Immediate upload (no confirm/cancel). JSON response."""
    sub = _own_submission(request)
    if not sub or sub.finished_at:
        return JsonResponse({'ok': False, 'error': 'جلسه یافت نشد.'}, status=403)
    section = request.POST.get('section', '')
    f = request.FILES.get('image')
    if section not in SECTION_KEYS or not f:
        return JsonResponse({'ok': False, 'error': 'فایل یا بخش نامعتبر است.'}, status=400)

    party = _own_party(request, sub, request.POST.get('party', ''))
    if party == 'invalid':
        return JsonResponse({'ok': False, 'error': 'زیان‌دیده یافت نشد.'}, status=400)

    # a one-time (timed) group is locked once its «تأیید نهایی» is done
    group = GROUP_BY_ID[SECTION_TO_GROUP[section]]
    _confirmed, locked = _group_state(_owner(sub, party), group)
    if locked:
        return JsonResponse({
            'ok': False,
            'error': 'این بخش تأیید نهایی شده است؛ امکان افزودن تصویر نیست.',
        }, status=400)

    try:
        with PILImage.open(f) as im:
            im.verify()  # ensure it really is an image
    except Exception:
        return JsonResponse({'ok': False, 'error': 'فایل انتخاب‌شده تصویر نیست.'}, status=400)

    rel = storage.save_case_image(request, sub, party, section, f)
    img = CaseImage.objects.filter(submission=sub, image_path=rel).first()
    log_activity('image_upload', request=request, method='POST',
                 description=(f'بارگذاری تصویر در بخش «{TITLE_BY_KEY.get(section, section)}»'
                              + (f' — زیان‌دیده {party.plate_number}' if party else ' — مقصر')),
                 object_label=(img.saved_name or img.original_name) if img else section)
    return JsonResponse({
        'ok': True,
        'image': {
            'id': img.pk,
            'url': f'/media/serve/{img.pk}/',
            'name': img.saved_name or img.original_name,
            'size': img.size_bytes,
            'watermarked': bool(img.watermarked_at),
        },
    })


@require_http_methods(['POST'])
def remove(request, image_id):
    img = _get_owned_image(request, image_id)
    if not img:
        return JsonResponse({'ok': False}, status=404)
    sub = img.submission
    group = GROUP_BY_ID[SECTION_TO_GROUP.get(img.section, '')] if img.section in SECTION_TO_GROUP else None
    if group is not None:
        _confirmed, locked = _group_state(_owner(sub, img.party), group)
        if locked:
            return JsonResponse({'ok': False, 'error': 'این بخش تأیید نهایی شده است.'}, status=400)
    log_activity('image_remove', request=request, method='POST',
                 description=f'حذف تصویر از بخش «{TITLE_BY_KEY.get(img.section, img.section)}»',
                 object_label=img.original_name)
    storage.remove_file(img.image_path)
    img.delete()
    return JsonResponse({'ok': True})


@require_http_methods(['POST'])
def confirm_group(request):
    """The group confirm buttons (v1.14).

    body: ``group`` (group_docs | group_plates | group_car) + ``party`` (empty =
    مقصر). The docs group may be confirmed again and again; the two timed
    groups are one-time and run the timing check first (a violation discards
    the group's images).
    """
    sub = _own_submission(request)
    if not sub or sub.finished_at:
        return JsonResponse({'ok': False, 'error': 'جلسه یافت نشد.'}, status=403)
    group = GROUP_BY_ID.get((request.POST.get('group') or '').strip())
    if not group:
        return JsonResponse({'ok': False, 'error': 'بخش نامعتبر است.'}, status=400)

    party = _own_party(request, sub, request.POST.get('party', ''))
    if party == 'invalid':
        return JsonResponse({'ok': False, 'error': 'زیان‌دیده یافت نشد.'}, status=400)
    owner = _owner(sub, party)
    confirmed, locked = _group_state(owner, group)

    if group['one_time_confirm'] and confirmed:
        return JsonResponse({
            'ok': False,
            'already': True,
            'error': 'تأیید نهایی این بخش قبلاً انجام شده است و فقط یک‌بار امکان‌پذیر است.',
        })

    # ---- completeness: at least SECTION_MIN photos per field of the group ---
    missing = []
    for key in group['sections']:
        n = CaseImage.objects.filter(**_owner_filter(owner)).filter(section=key).count()
        if n < SECTION_MIN[key]:
            missing.append(TITLE_BY_KEY[key])
    if missing:
        return JsonResponse({
            'ok': False,
            'error': 'برای تأیید این بخش، همهٔ موارد لازم باید تصویر داشته باشند: '
                     + '، '.join(missing) + '.',
        })

    # ---- timed groups: the gap/span rule (the same seconds in every part) ---
    if group['timed']:
        from app_core import dev_settings

        min_total = sum(SECTION_MIN[k] for k in group['sections'])
        status, message = timing.evaluate(
            owner, group['sections'],
            gap_seconds=dev_settings.get(request, 'CAR_IMAGE_MAX_GAP_SECONDS'),
            span_minutes=dev_settings.get(request, 'CAR_IMAGE_MAX_SPAN_MINUTES'),
            min_required=min_total,
        )
        if status in (timing.STATUS_GAP, timing.STATUS_SPAN):
            removed = timing.discard_group(owner, group['sections'])
            log_activity('car_confirm', request=request, method='POST',
                         description=f'لغو بخش «{group["title"]}» به‌دلیل زمان‌بندی '
                                     f'({removed} تصویر حذف شد)',
                         object_label=f'{removed} تصویر')
            return JsonResponse({
                'ok': False, 'car_group_reset': True, 'removed': removed, 'message': message,
            })

    # ---- store the confirmation ------------------------------------------- #
    now = timezone.now()
    if group['id'] == 'group_docs':
        owner.docs_confirmed_at = now
        fields = ['docs_confirmed_at']
    elif group['id'] == 'group_plates':
        owner.plates_confirmed = True
        owner.plates_confirmed_at = now
        fields = ['plates_confirmed', 'plates_confirmed_at']
    else:
        owner.car_confirmed = True
        owner.car_confirmed_at = now
        fields = ['car_confirmed', 'car_confirmed_at']
    owner.save(update_fields=fields)

    count = CaseImage.objects.filter(**_owner_filter(owner)).filter(
        section__in=group['sections']).count()
    log_activity('car_confirm', request=request, method='POST',
                 description=f'تأیید بخش «{group["title"]}» ({count} تصویر)'
                             + (' — تأیید دوباره' if confirmed else ''),
                 object_label=f'{count} تصویر')
    return JsonResponse({'ok': True, 'confirmed_at': now.isoformat(),
                         'repeatable': not group['one_time_confirm']})


def _owner_filter(owner):
    if hasattr(owner, 'submission_id'):          # DamagedParty
        return {'party': owner}
    return {'submission': owner, 'party__isnull': True}


@require_GET
def serve(request, image_id):
    """Serve an uploaded image to its owner only."""
    img = _get_owned_image(request, image_id)
    if not img:
        raise Http404
    path = storage.root() / img.image_path
    if not path.exists() or not path.is_file():
        raise Http404
    import mimetypes
    ctype = (_IMAGE_TYPES.get(path.suffix.lower())
             or mimetypes.guess_type(path.name)[0]
             or 'image/jpeg')
    resp = FileResponse(open(path, 'rb'), content_type=ctype)
    resp['Content-Disposition'] = f'inline; filename="{path.name}"'
    # v1.17 — never cache a photo URL: finalize stamps the files IN PLACE and
    # the URL stays the same, so a cached copy would keep showing the
    # unstamped image («واترمارک دیده نمی‌شود»).
    resp['Cache-Control'] = 'private, no-store, max-age=0'
    resp['Expires'] = '0'
    return resp
