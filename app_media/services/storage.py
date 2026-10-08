"""Storage service (v1.14 owner layout).

Every day gets its own folder under ``storage/files`` named after the **Jalali
date** of the day; every case gets a folder named after its «کد رایانه پرونده»
that **ends with the username** of the user working on it; every زیان‌دیده gets
a subfolder named after their «شماره پلاک»::

    storage/files/<date>/<کد رایانه>-<username>/<field>.jpg                  (مقصر)
    storage/files/<date>/<کد رایانه>-<username>/<شماره پلاک>/<field>.jpg     (زیان‌دیده)

``<field>`` is the name of the upload field the photo was taken for —
``license_front.jpg``, ``car_card_back.jpg``, ``chassis_number.jpg``,
``plate_front.jpg``, ``car_shots.jpg`` (a second photo of the same field gets
``-2``, ``-3``, …). The watermark is burned in **as the photo is written**.
"""
import os
import re
import shutil
import unicodedata
from pathlib import Path

from django.conf import settings

from app_core.utils.jalali import TEHRAN, gregorian_to_jalali_str
from django.utils import timezone

SAFE_NAME_RE = re.compile(r'[^A-Za-z0-9._-]+')

#: every finished case lives under this folder inside the storage root
FINAL_SUBDIR = 'files'


def root() -> Path:
    p = Path(settings.STORAGE_ROOT)
    p.mkdir(parents=True, exist_ok=True)
    return p


def safe_name(name: str) -> str:
    s = unicodedata.normalize('NFKC', str(name or 'image'))
    s = SAFE_NAME_RE.sub('_', s)[-80:]
    return s or 'image'


def _unique_name(folder: Path, name: str) -> str:
    """``name``, or ``name-2``/``-3``… when the same name already exists."""
    stem, suffix = Path(name).stem, Path(name).suffix
    candidate, counter = name, 1
    while (folder / candidate).exists():
        counter += 1
        candidate = f'{stem}-{counter}{suffix}'
    return candidate


# --------------------------------------------------------------------------- #
# the folder layout
# --------------------------------------------------------------------------- #
def date_token(when=None) -> str:
    """``1405-07-02`` — the Jalali date of the day (folder-safe)."""
    from django.utils import timezone as tz
    dt = when or tz.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, TEHRAN)
    dt = timezone.localtime(dt, TEHRAN)
    return gregorian_to_jalali_str(dt.year, dt.month, dt.day).replace('/', '-')


def submission_date_token(submission) -> str:
    """The day folder of a case — fixed on the day the case was found."""
    return date_token(getattr(submission, 'created_at', None))


def case_dir(submission) -> Path:
    """``storage/files/<date>/<کد رایانه>-<username>`` — the case folder.

    The name carries the «کد رایانه پرونده» (as required) and ends with the
    username of the user that works on the case (the folders page only lists
    the folders that end with the logged-in username).
    """
    code = str(submission.computer_code or 'case').strip() or 'case'
    code = re.sub(r'[\\/:*?"<>|\s,]+', '-', code)
    user = str(getattr(submission, 'auth_username', '') or 'user').strip() or 'user'
    user = re.sub(r'[\\/:*?"<>|\s,]+', '-', user)
    return root() / FINAL_SUBDIR / submission_date_token(submission) / f'{code}-{user}'


def party_dir(submission, party) -> Path:
    """``…/<case>/<شماره پلاک>`` — the folder of one زیان‌دیده."""
    plate = re.sub(r'[\\/:*?"<>|\s,]+', '-', str(party.plate_number or '').strip()) or 'party'
    return case_dir(submission) / plate


def owner_dir(submission, party=None) -> Path:
    return party_dir(submission, party) if party is not None else case_dir(submission)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_case_dir(submission) -> Path:
    """Create the case folder at «یافتن پرونده» time (owner request)."""
    return ensure_dir(case_dir(submission))


def clean_case_dir(submission) -> None:
    """Remove the whole case folder (all زیان‌دیدگان included)."""
    d = case_dir(submission)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        parent = d.parent
        try:
            if parent.exists() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass


# --------------------------------------------------------------------------- #
# writing a photo
# --------------------------------------------------------------------------- #
def field_name(section: str, ext: str) -> str:
    """The file name of a photo = the name of its field (e.g. car_card_front.jpg)."""
    ext = ext if str(ext).startswith('.') else f'.{ext}'
    return f'{safe_name(section)}{ext}'


def save_case_image(request, submission, party, section, uploaded_file):
    """Store one uploaded photo in its final folder, named by field.

    Writes into ``…/<کد رایانه>-<username>/`` (مقصر) or ``…/<شماره پلاک>/``
    (زیان‌دیده) right away — the file name is the field name
    (``car_card_front.jpg`` …). Returns the path relative to ``storage/``.

    v1.14.1 — the photo is stored **raw**: the watermark program is activated
    when the upload is finalized (``watermark.run_simple_for_submission``).

    v1.15 — no duplicates, ever (owner request): a single-photo field keeps
    exactly one file — uploading it again **replaces** the previous photo; and
    the staged ``*.upload`` file is **moved** into place (never copied), so the
    folder cannot end up with the same photo twice.
    """
    from ..constants import MULTI_PHOTO_SECTIONS
    from ..models import CaseImage
    from . import watermark

    folder = ensure_dir(owner_dir(submission, party))

    suffix = Path(uploaded_file.name or '').suffix.lower()
    if suffix not in ('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff'):
        suffix = '.jpg'

    name = _unique_name(folder, field_name(section, suffix))
    target = folder / name
    staging = folder / (name + '.upload')
    try:
        with open(staging, 'wb') as out:
            for chunk in uploaded_file.chunks():
                out.write(chunk)

        # the extension follows the real content (browsers often send «image»)
        real_suffix = watermark.extension_for(staging, suffix)
        if real_suffix != suffix:
            suffix = real_suffix

        # v1.14.1 — no stamp at upload time; «کد رایانه» is burned in at finalization
        stamped_at = None

        # v1.15 — single-photo fields: the new upload replaces the old photo
        if section not in MULTI_PHOTO_SECTIONS:
            for old in CaseImage.objects.filter(submission=submission, party=party,
                                                section=section):
                remove_file(old.image_path)
                old.delete()

        # the final name is computed *after* the replacement above, so a
        # replaced field keeps its plain name (car_card_front.jpg, no «-2»)
        name = _unique_name(folder, field_name(section, suffix))
        target = folder / name
        os.replace(staging, target)          # move — the staging never lingers
    except Exception:
        if staging.exists():
            try:
                staging.unlink()
            except OSError:
                pass
        raise

    CaseImage.objects.create(
        submission=submission,
        party=party,
        section=section,
        image_path=str(target.relative_to(root())).replace('\\', '/'),
        original_name=str(uploaded_file.name)[:255],
        saved_name=name[:255],
        size_bytes=target.stat().st_size or (uploaded_file.size or 0),
        watermarked_at=stamped_at,
    )
    return str(target.relative_to(root())).replace('\\', '/')


def remove_file(rel_path):
    try:
        p = root() / rel_path
        if p.exists() and p.is_file():
            p.unlink()
    except OSError:
        pass


def unique_number_for(jalali_date_str) -> str:
    """Unique case number: DN-<JJJJ>-<MM>-<DD>-<6 alnum>, e.g. DN-1405-06-31-K7P2QX.

    ASCII (filesystem-safe); the date is the Jalali finish date.
    """
    import secrets

    alphabet = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
    y, m, d = (p for p in str(jalali_date_str).split('/')[:3])
    from app_main.models import CaseSubmission
    for _ in range(25):
        tail = ''.join(secrets.choice(alphabet) for _ in range(6))
        candidate = f'DN-{y}-{m}-{d}-{tail}'
        if not CaseSubmission.objects.filter(unique_number=candidate).exists():
            return candidate
    raise RuntimeError('Could not generate a unique number')
