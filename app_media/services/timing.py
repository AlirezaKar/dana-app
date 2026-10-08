"""Group timing validation (spec.md C6, v1.14).

Rule (owner-confirmed): inside a **timed group** («شماره شاسی و پلاک‌ها» or
«اطراف ماشین») every consecutive upload must be at most
CAR_IMAGE_MAX_GAP_SECONDS (default 10 s) apart, and the first-to-last span must
stay under CAR_IMAGE_MAX_SPAN_MINUTES (10 min). The numbers are the same across
all parts and come from `.env` (or the live development override,
``app_core/dev_settings.py``) — the caller passes the values in force.

The check runs when the user presses the group's «تأیید نهایی» button (one-time
per group); a violation discards the whole group's images so they can be
retaken. G1 («پشت و رو گواهینامه و کارت ماشین») is exempt — its timestamps
are still stored. The rules apply identically to مقصر and to every زیان‌دیده.
"""
from datetime import timedelta

from app_core.utils.digits import to_fa

from ..constants import CAR_IMAGE_MAX_GAP_SECONDS, CAR_IMAGE_MAX_SPAN_MINUTES
from ..models import CaseImage

STATUS_PENDING = 'pending'   # group not complete yet
STATUS_OK = 'ok'
STATUS_NOT_CONFIRMED = 'not_confirmed'
STATUS_GAP = 'gap_error'
STATUS_SPAN = 'span_error'


def group_images(owner, sections):
    """The images of one timed group — ``owner`` is a CaseSubmission or a DamagedParty."""
    sections = list(sections)
    if getattr(owner, 'plate_number', None) is not None and hasattr(owner, 'submission_id'):
        qs = CaseImage.objects.filter(party=owner, section__in=sections)
    else:
        qs = CaseImage.objects.filter(submission=owner, party__isnull=True, section__in=sections)
    return qs.order_by('uploaded_at')


def evaluate(owner, sections, gap_seconds=None, span_minutes=None, min_required=2):
    """Returns (status, message) for a timed group of a party.

    ``gap_seconds`` / ``span_minutes`` are the limits in force (`.env` or the
    development override); ``None`` keeps the configured defaults.
    """
    gap_seconds = CAR_IMAGE_MAX_GAP_SECONDS if gap_seconds is None else int(gap_seconds)
    span_minutes = CAR_IMAGE_MAX_SPAN_MINUTES if span_minutes is None else int(span_minutes)
    imgs = list(group_images(owner, sections))
    if len(imgs) < min_required:
        return STATUS_PENDING, ''
    times = [i.uploaded_at for i in imgs]
    gap_limit = timedelta(seconds=gap_seconds)
    span_limit = timedelta(minutes=span_minutes)
    max_gap = max((b - a for a, b in zip(times, times[1:])), default=timedelta(0))
    span = times[-1] - times[0]
    if max_gap > gap_limit:
        over = int(max_gap.total_seconds())
        return STATUS_GAP, (
            f'زمان زیادی طول کشید! فاصله بین دو تصویر {to_fa(over)} ثانیه بوده '
            f'(حداکثر مجاز {to_fa(gap_seconds)} ثانیه). '
            'تصاویر این بخش حذف شدند — لطفاً دوباره و پشت سر هم عکس بگیرید.'
        )
    if span > span_limit:
        return STATUS_SPAN, (
            f'زمان زیادی طول کشید! مجموع زمان عکس‌گیری بیش از '
            f'{to_fa(span_minutes)} دقیقه شده است. '
            'تصاویر این بخش حذف شدند — لطفاً دوباره تلاش کنید.'
        )
    return STATUS_OK, ''


def discard_group(owner, sections, remove_files=True):
    """Delete every image of the group (files + rows). Returns the count."""
    qs = group_images(owner, sections)
    count = qs.count()
    if remove_files:
        from . import storage
        for img in qs:
            storage.remove_file(img.image_path)
    qs.delete()
    return count
