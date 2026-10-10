"""Image watermarking — the **single watermark module** of the project (v1.18).

Everything watermark-related lives here: the drawing code, the metadata
comment, the environment check and the runnable script (the old ``watermark.sh``
/ ``manage.py watermark_images`` twins are gone — the app runs on **Windows**,
so the entry point is this python module).

The app's watermark program is :func:`run_simple_for_submission`, which runs
**at finalization** and stamps every photo of the case in place with a
transparent stamp in the bottom-right corner (no box, no background): the two
brand logos plus the case facts —

    کد رایانه: …   شماره پرونده: …
    نام کاربری: …   تاریخ و ساعت: … (Jalali)

There is **no GPS section** any more (owner request). v1.18 adds an **optional
QR code** left of the texts: it encodes the public ``wm_info`` page URL
(``code`` / ``case`` / ``user`` / ``at`` query args). The QR needs the
``qrcode`` package (``qrcode[pil]`` in ``requirements.txt``) — if the package
is missing or anything about the QR fails, **the text watermark is stamped
anyway** (fail-safe, never breaks the system).

Two entry points:

* **automatic** — :func:`run_simple_for_submission` is called by ``finish``
  (and :func:`simple_watermark_file` can stamp one file directly);
* **manual** — run this module at any time over photos already on disk::

      python -m app_media.services.watermark                # photos not stamped yet
      python -m app_media.services.watermark --all          # every photo
      python -m app_media.services.watermark --case 22208730
      python -m app_media.services.watermark --all --out D:\\stamped
      python -m app_media.services.watermark --path storage/files --dry-run

Only Pillow is used for drawing (raqm-enabled, so Persian text is shaped and
joined correctly). The font is the same self-hosted **Vazir** family as the
site, converted to TTF for PIL (:func:`ensure_fonts` does that automatically).
The legacy styled stamp (:func:`watermark_file`) is kept for the CLI; every
call is wrapped by the caller, so a watermark problem can never break a
finalize step.
"""
import logging
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from app_core.utils.digits import to_fa
from app_core.utils.jalali import TEHRAN, gregorian_to_jalali_str

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# config
# --------------------------------------------------------------------------- #
DEFAULTS = {
    'ENABLED': True,
    'POSITION': 'bottom-right',     # bottom-right | bottom-left | top-right | top-left
    'OPACITY': 0.85,                # whole stamp (0..1) — transparent, no background
    'SCALE': 1.0,                   # 1.0 = default size (font ≈ 2.6 % of the short side)
    'MIN_WIDTH_FRACTION': 0.55,     # stamp is never wider than this share of the image
    'MAX_HEIGHT_FRACTION': 0.38,    # … nor taller than this share of the height
    'LINE_SPACING': 1.35,
    'LOGOS': ['img/dana-logo.png', 'img/hef.co.ir.png'],
    'LOGO_HEIGHT_FRACTION': 0.055,  # logo height = 5.5 % of the image height
    'MARGIN_FRACTION': 0.022,       # distance from the image border
    'JPEG_QUALITY': 95,
    'QR_MIN_SIDE': 88,   # smaller QRs are unscannable — skipped entirely
    'QR_ENABLED': True,          # v1.20 — .env toggle for the QR code
    'CUSTOM_TEXT': '',           # v1.20 — free text stamped under the values
    'CUSTOM_TEXT_ENABLED': True, # v1.20 — .env toggle for the custom text
    # every line of the stamp (logos cannot be text) is written into the image's
    # comment/metadata block as well — Windows: Properties → Details → Comments
    'WRITE_COMMENT': True,
}

#: labels of the info lines (Persian, in the order they are drawn)
LABEL = {
    'when': 'تاریخ و ساعت',
    'computer_code': 'کد رایانه پرونده',
    'case_number': 'شماره پرونده',
    'plate': 'شماره پلاک',
    'policy': 'شماره بیمه نامه',
    'username': 'نام کاربری',
}


def config() -> dict:
    """``settings.WATERMARK`` merged over :data:`DEFAULTS`."""
    merged = dict(DEFAULTS)
    merged.update(getattr(settings, 'WATERMARK', None) or {})
    return merged


#: file extensions treated as photos
#: (v1.21 — HEIC/HEIF/DNG belong to the accepted uploads; Pillow cannot open
#: them, so the stamping step skips those files.)
IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff',
                  '.heic', '.heif', '.dng'}


#: Pillow format → the extension we save it with
EXTENSION_BY_FORMAT = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'BMP': '.bmp',
                       'TIFF': '.tiff', 'GIF': '.gif'}


def extension_for(path, fallback: str = '.jpg') -> str:
    """The extension that matches the **content** of an uploaded file.

    A photo sent by a phone browser is often called ``image`` (no extension) or
    carries a wrong one; the saved file must still be named after what it is.
    """
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as im:
            return EXTENSION_BY_FORMAT.get((im.format or '').upper(), fallback)
    except Exception:
        return fallback


def is_image_name(path) -> bool:
    """True when a path looks like an image (by extension)."""
    return Path(str(path)).suffix.lower() in IMAGE_SUFFIXES


def _static_sources() -> Path:
    """The project-wide ``statics/`` folder (``settings.STATIC_SOURCES``, v1.16)."""
    return Path(getattr(settings, 'STATIC_SOURCES', Path(settings.BASE_DIR) / 'statics'))


def _font_dir() -> Path:
    # v1.16 — resolved through settings (the ``font`` prefix of
    # STATICFILES_DIRS) instead of a hardcoded app folder.
    for entry in getattr(settings, 'STATICFILES_DIRS', ()) or ():
        try:
            prefix, directory = entry
        except (TypeError, ValueError):
            continue
        if prefix == 'font':
            return Path(directory)
    return _static_sources() / 'font'


def _static_dir() -> Path:
    return _static_sources()


# --------------------------------------------------------------------------- #
# fonts (the TTF twin of the self-hosted Vazir woff2 files)
# --------------------------------------------------------------------------- #
def ensure_fonts() -> list:
    """Make sure the Vazir TTF fonts Pillow needs exist (v1.14 — replaces the
    old shell snippet of ``watermark.sh``). Returns the problems found."""
    problems = []
    weights = ('400', '500', '700', '900')
    missing = [w for w in weights if not (_font_dir() / f'Vazir-{w}.ttf').exists()]
    if not missing:
        return problems
    try:
        from fontTools.ttLib import TTFont          # pip install "fonttools[woff]" brotli
    except ImportError:
        for w in missing:
            src = _font_dir() / f'Vazir-{w}.woff2'
            if src.exists():
                problems.append(
                    f'فونت TTF موجود نیست و fonttools نصب نیست — '
                    f'pip install "fonttools[woff]" brotli  (برای ساخت {src.stem}.ttf)')
        return problems
    for w in missing:
        src = _font_dir() / f'Vazir-{w}.woff2'
        if not src.exists():
            continue
        try:
            font = TTFont(str(src))
            font.flavor = None                       # woff2 → plain TTF
            font.save(str(_font_dir() / f'Vazir-{w}.ttf'))
        except Exception as exc:                     # brotli missing, file broken, …
            problems.append(f'ساخت فونت {src.stem}.ttf ممکن نشد ({exc})')
    return problems


# --------------------------------------------------------------------------- #
# the facts that go into the stamp
# --------------------------------------------------------------------------- #
@dataclass
class WatermarkInfo:
    """Everything the stamp shows (all optional — missing lines are skipped).

    v1.14 — logos + the six text lines only, **no GPS**.
    """

    username: str = ''
    computer_code: str = ''
    case_number: str = ''
    plate_number: str = ''
    policy_number: str = ''
    captured_at: datetime | None = None

    def when_text(self) -> str:
        """Jalali date + time in Tehran, Persian digits: ``۱۴۰۵/۰۷/۰۱ ۱۶:۴۵``."""
        dt = self.captured_at or timezone.now()
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, TEHRAN)
        dt = timezone.localtime(dt, TEHRAN)
        date = gregorian_to_jalali_str(dt.year, dt.month, dt.day)
        return to_fa(f'{date} {dt.strftime("%H:%M")}')

    def lines(self) -> list:
        """``[(key, value), …]`` — only the filled lines, in drawing order."""
        order = [
            ('when', self.when_text() if self.captured_at else ''),
            ('computer_code', self.computer_code),
            ('case_number', self.case_number),
            ('plate', self.plate_number),
            ('policy', self.policy_number),
            ('username', self.username),
        ]
        out = []
        for key, value in order:
            value = str(value or '').strip()
            if value:
                out.append((key, value))
        return out

    def display_lines(self) -> list:
        """``[(Persian label, value), …]`` — for reports and tests."""
        return [(LABEL[key], value) for key, value in self.lines()]

    def comment_text(self) -> str:
        """The whole stamp as one comma-separated line, for the image metadata.

        Logos cannot be stored as text, everything else is — the same values the
        watermark prints, so the «Properties → Details → Comments» field and the
        visible stamp always agree.
        """
        return ', '.join(f'{LABEL[key]}: {value}' for key, value in self.lines())

    # ---- builders -------------------------------------------------------- #
    @classmethod
    def from_submission(cls, submission, *, username='', party=None,
                        captured_at=None) -> 'WatermarkInfo':
        """Build the stamp data from an in-progress case (upload time).

        ``party`` — a :class:`app_main.DamagedParty`: its «شماره پلاک» replaces
        the case plate on that party's photos.
        """
        record = getattr(submission, 'any_record', None)
        kind = getattr(submission, 'insurance_type', '')
        body = kind == 'body'
        plate = ''
        policy = ''
        if record is not None:
            number = (record.plate_number or '').strip()
            serial = (getattr(record, 'plate_serial', '') or '').strip()
            plate = f'{number}-{serial}' if (number and serial) else (number or serial)
            policy = ((getattr(record, 'policy_number', '') if body
                       else getattr(record, 'atfault_policy_number', '') or '').strip())
        plate = plate or getattr(submission, 'plate_value', '') or ''
        if party is not None:
            # v1.21 — a زیان‌دیده keeps its plate the way the tables do: the
            # main part + the «ایران ##» serial, shown here as «94س225-63».
            number = (getattr(party, 'plate_number', '') or '').strip()
            serial = (getattr(party, 'plate_serial', '') or '').strip()
            if number:
                plate = f'{number}-{serial}' if serial else number
        return cls(
            username=username or getattr(submission, 'auth_username', ''),
            computer_code=(getattr(submission, 'entered_file_code', '')
                           or (getattr(record, 'computer_code', '') if record else '')),
            case_number=(getattr(record, 'case_number', '') if record else ''),
            plate_number=plate,
            policy_number=policy,
            captured_at=captured_at,
        )

    @classmethod
    def from_image(cls, image, submission=None, party=None) -> 'WatermarkInfo':
        """Build the stamp data of an already stored image (manual re-run).

        Works without a database row too (``--path`` on a bare folder): then
        only the upload time is printed.
        """
        submission = submission or getattr(image, 'submission', None)
        if submission is None:
            return cls(captured_at=getattr(image, 'uploaded_at', None))
        return cls.from_submission(
            submission,
            username=getattr(submission, 'auth_username', ''),
            party=party or getattr(image, 'party', None),
            captured_at=getattr(image, 'uploaded_at', None),
        )


# --------------------------------------------------------------------------- #
# drawing
# --------------------------------------------------------------------------- #
def _font(size: int, weight: str = '700'):
    """Vazir TTF of the requested weight (converted from the self-hosted woff2)."""
    from PIL import ImageFont
    for candidate in (weight, '700', '400'):
        path = _font_dir() / f'Vazir-{candidate}.ttf'
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception:
                continue
    return _font_default(size)


def _font_default(size: int):
    """Pillow's bundled font — always available (v1.17 watermark fallback)."""
    from PIL import ImageFont
    try:
        return ImageFont.load_default(size)
    except TypeError:            # Pillow < 10.1 ignores the size argument
        return ImageFont.load_default()


def _logo(path: Path, height: int):
    """A logo file as an RGBA image scaled to ``height`` px (or ``None``)."""
    from PIL import Image
    try:
        with Image.open(path) as im:
            logo = im.convert('RGBA')
    except Exception:
        return None
    ratio = height / max(1, logo.height)
    return logo.resize((max(1, int(logo.width * ratio)), max(1, height)), Image.LANCZOS)


def _text_size(draw, text, font, rtl=True):
    kwargs = {'direction': 'rtl', 'language': 'fa'} if rtl else {}
    box = draw.textbbox((0, 0), text, font=font, **kwargs)
    return box[2] - box[0], box[3] - box[1]


def build_overlay(size, info: WatermarkInfo, cfg: dict):
    """Render the transparent stamp as an RGBA image fitted to ``size``.

    v1.14 — logos first (top, right-aligned like the text) and the six fact
    lines below; no GPS row and no maps URL.
    """
    from PIL import Image, ImageDraw

    width, height = size
    short = min(width, height)
    scale = float(cfg.get('SCALE') or 1.0)
    font_size = max(11, int(short * 0.026 * scale))
    small_size = max(10, int(font_size * 0.86))
    label_font = _font(small_size, '500')
    value_font = _font(font_size, '700')
    font_direction = {'direction': 'rtl', 'language': 'fa'}

    lines = info.lines()

    measure = ImageDraw.Draw(Image.new('RGBA', (8, 8)))
    gap = max(4, int(font_size * 0.42))
    line_height = int(font_size * float(cfg.get('LINE_SPACING') or 1.35))

    # ---------------------------------------------------------- text rows ---
    def make_rows():
        out = []
        for key, value in lines:
            out.append((f'{LABEL[key]}:', value, line_height))
        return out

    rows = make_rows()

    # ------------------------------------------------------------ logos -----
    logo_height = max(14, int(height * float(cfg.get('LOGO_HEIGHT_FRACTION') or 0.055) * scale))
    logos = [l for l in (_logo(_static_dir() / rel, logo_height) for rel in cfg.get('LOGOS') or [])
             if l is not None]

    def measure_width(the_rows, the_logos, the_gap):
        w = 0
        for label, value, _h in the_rows:
            lw, _ = _text_size(measure, label, label_font)
            vw, _ = _text_size(measure, value, value_font)
            w = max(w, lw + the_gap + vw)
        if the_logos:
            w = max(w, sum(l.width for l in the_logos) + the_gap * (len(the_logos) - 1))
        return w

    # ------------------------------------------------------------ width -----
    widest = measure_width(rows, logos, gap)
    max_width = int(width * float(cfg.get('MIN_WIDTH_FRACTION') or 0.55))
    if widest > max_width and widest > 0:      # shrink everything uniformly
        ratio = max_width / widest
        font_size = max(9, int(font_size * ratio))
        small_size = max(8, int(small_size * ratio))
        label_font, value_font = _font(small_size, '500'), _font(font_size, '700')
        line_height = max(10, int(line_height * ratio))
        logo_height = max(12, int(logo_height * ratio))
        logos = [l for l in (_logo(_static_dir() / rel, logo_height)
                             for rel in cfg.get('LOGOS') or []) if l is not None]
        rows = make_rows()

    pad = max(6, int(font_size * 0.6))
    content_width = measure_width(rows, logos, gap)
    content_height = sum(h for _l, _v, h in rows) + (logo_height + gap if logos else 0)
    canvas = (max(10, content_width + pad * 2), max(10, content_height + pad * 2))

    # a low-resolution photo must not be swallowed by the stamp: shrink once if
    # the stamp is taller than MAX_HEIGHT_FRACTION of the image
    max_height = int(height * float(cfg.get('MAX_HEIGHT_FRACTION') or 0.38))
    if max_height and canvas[1] > max_height:
        ratio = max(0.6, max_height / canvas[1])
        font_size = max(9, int(font_size * ratio))
        small_size = max(8, int(small_size * ratio))
        label_font, value_font = _font(small_size, '500'), _font(font_size, '700')
        gap = max(3, int(gap * ratio))
        line_height = max(9, int(line_height * ratio))
        logo_height = max(12, int(logo_height * ratio))
        logos = [l for l in (_logo(_static_dir() / rel, logo_height)
                             for rel in cfg.get('LOGOS') or []) if l is not None]
        pad = max(5, int(pad * ratio))
        rows = make_rows()
        content_width = measure_width(rows, logos, gap)
        content_height = sum(h for _l, _v, h in rows) + (logo_height + gap if logos else 0)
        canvas = (max(10, content_width + pad * 2), max(10, content_height + pad * 2))

    # ----------------------------------------------------------- render -----
    overlay = Image.new('RGBA', canvas, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    y = pad
    if logos:                       # logos first (right aligned, like the text)
        x = canvas[0] - pad - sum(l.width for l in logos) - gap * (len(logos) - 1)
        for logo in logos:
            overlay.alpha_composite(logo, (int(x), int(y)))
            x += logo.width + gap
        y += logo_height + gap

    for label, value, h in rows:
        baseline = y
        lw, _ = _text_size(draw, label, label_font)
        vw, _ = _text_size(draw, value, value_font)
        x = canvas[0] - pad
        draw.text((x, baseline), label, font=label_font, fill=(255, 255, 255, 235),
                  anchor='ra', **font_direction)
        draw.text((x - lw - gap, baseline), value, font=value_font, fill=(255, 255, 255, 255),
                  anchor='ra', **font_direction)
        y += h

    # a soft dark halo behind the white text/logos so it stays readable on any photo
    halo = Image.new('RGBA', canvas, (0, 0, 0, 0))
    alpha = overlay.getchannel('A')
    from PIL import ImageFilter
    shadow = Image.new('RGBA', canvas, (0, 0, 0, 0))
    shadow.putalpha(alpha.filter(ImageFilter.GaussianBlur(max(2, font_size // 5))))
    halo = Image.alpha_composite(halo, shadow)
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        shifted = Image.new('RGBA', canvas, (0, 0, 0, 0))
        shifted.paste(shadow, (dx, dy))
        halo = Image.alpha_composite(halo, shifted)
    halo = Image.blend(Image.new('RGBA', canvas, (0, 0, 0, 0)), halo, 0.75)

    stamp = Image.alpha_composite(halo, overlay)

    # overall transparency of the whole stamp
    opacity = float(cfg.get('OPACITY') if cfg.get('OPACITY') is not None else 0.85)
    if opacity < 1.0:
        alpha = stamp.getchannel('A').point(lambda v: int(v * opacity))
        stamp.putalpha(alpha)
    return stamp


def _position(stamp, size, cfg: dict):
    """Top-left corner of the stamp for the configured corner."""
    width, height = size
    margin = max(6, int(min(width, height) * float(cfg.get('MARGIN_FRACTION') or 0.022)))
    where = str(cfg.get('POSITION') or 'bottom-right').lower()
    x = margin if 'left' in where else width - stamp.width - margin
    y = margin if 'top' in where else height - stamp.height - margin
    return max(0, x), max(0, y)


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #
def watermark_image(pil_image, info: WatermarkInfo, cfg: dict | None = None):
    """Return a watermarked copy of a PIL image (RGBA in, RGBA out)."""
    cfg = cfg or config()
    base = pil_image.convert('RGBA')
    stamp = build_overlay(base.size, info, cfg)
    out = base.copy()
    out.alpha_composite(stamp, _position(stamp, base.size, cfg))
    return out


def preflight() -> list:
    """Reasons the stamp could not be drawn (empty list = everything is fine).

    Checked by the CLI so a broken environment reports itself instead of
    silently storing un-stamped photos.
    """
    problems = list(ensure_fonts())
    from PIL import features
    try:
        if not features.check('raqm'):
            problems.append('Pillow بدون پشتیبانی raqm نصب است؛ متن فارسی درست شکل نمی‌گیرد '
                            '(pip install --upgrade --force-reinstall Pillow)')
    except Exception:
        pass
    if not (_font_dir() / 'Vazir-700.ttf').exists():
        problems.append(f'فونت TTF پیدا نشد: {_font_dir() / "Vazir-700.ttf"}')
    for rel in config().get('LOGOS') or []:
        if not (_static_dir() / rel).exists():
            problems.append(f'لوگو پیدا نشد: {_static_dir() / rel}')
    return problems


def _metadata_block(pil_image, info: WatermarkInfo, cfg: dict, reset_orientation: bool = True):
    """``(exif_bytes | None, comment_bytes | None)`` for the metadata of the file.

    * ``ImageDescription`` — shows up in most file managers;
    * ``UserComment`` — the standard “user note” field;
    * ``XPComment`` (UTF-16LE) — what **Windows Explorer** shows as
      *Properties → Details → Comments*;
    * the JPEG comment marker / the PNG ``Comment`` text chunk.

    ``reset_orientation`` is set when the pixels were already rotated upright by
    the stamping pass; the comment-only pass leaves the original orientation tag
    alone (it never touches the pixels).
    """
    if not cfg.get('WRITE_COMMENT', True):
        return None, None
    text = info.comment_text()
    if not text:
        return None, None

    try:
        exif = pil_image.getexif()
    except Exception:
        exif = None
    if exif is None:
        from PIL import Image
        exif = Image.Exif()
    # the pixels are already upright (exif_transpose) — never let a viewer rotate
    # them a second time.
    # UserComment / ImageDescription are written as raw bytes with the right
    # charset marker, so viewers that understand them show the Persian text
    # instead of question marks (v1.13).
    try:
        if reset_orientation:
            exif[0x0112] = 1                   # Orientation = normal
        exif[0x010E] = text.encode('utf-8')                        # ImageDescription
        exif[0x9286] = b'UNICODE\x00' + text.encode('utf-16-le')     # UserComment (UTF-16LE)
        exif[0x9C9C] = text.encode('utf-16-le') + b'\x00\x00'       # XPComment — «Comments» in Windows
        exif_bytes = exif.tobytes()
    except Exception:
        exif_bytes = None
    return exif_bytes, text.encode('utf-8')


def _atomic_put(save_fn, out_path) -> None:
    """Render to a temporary neighbour, then move the result into place.

    The move is retried a few times (on Windows an antivirus/indexer can hold
    the fresh file for a moment) and the scratch file is always cleaned up —
    after watermarking only the stamped photo may remain on disk (owner
    request). Any failure raises, so an unstamped photo stays unstamped and
    can be re-run instead of silently duplicating files.
    """
    import os
    import time

    scratch = out_path.with_name(out_path.name + '.wm-tmp')
    try:
        save_fn(scratch)
        for attempt in range(3):
            try:
                os.replace(scratch, out_path)
                return
            except OSError:
                if attempt == 2:
                    raise
                time.sleep(0.25 * (attempt + 1))
    finally:
        if scratch.exists() and scratch != out_path:
            for attempt in range(3):
                try:
                    scratch.unlink()
                    break
                except OSError:
                    if attempt == 2:
                        break
                    time.sleep(0.25 * (attempt + 1))


def watermark_file(path, info: WatermarkInfo, cfg: dict | None = None, dest=None) -> Path:
    """Watermark the file at ``path`` (in place, or into ``dest``).

    Draws the transparent stamp **and** writes the same facts into the image
    metadata (comment) in a single re-encode. The original format is kept (JPEG
    is re-saved with quality 92, the camera EXIF is preserved). The result is
    written to a temporary neighbour and only then moved into place, so a
    failure can never destroy the source photo. Returns the written path.
    """
    import os

    from PIL import Image, ImageOps
    cfg = cfg or config()
    src = Path(path)
    out_path = Path(dest) if dest else src
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        fmt = (im.format or 'JPEG').upper()
        icc = im.info.get('icc_profile')
        image = ImageOps.exif_transpose(im.convert('RGBA'))
        if image is None:                      # exif_transpose returns None if in-place
            image = im.convert('RGBA')
        metadata_source = image.copy()         # keeps the (upright) EXIF for _metadata_block

    out = watermark_image(image, info, cfg).convert('RGB' if fmt in ('JPEG', 'JPG') else 'RGBA')
    exif_bytes, comment = _metadata_block(metadata_source, info, cfg)
    save_kwargs = {}
    if fmt in ('JPEG', 'JPG'):
        save_kwargs = {'quality': int(cfg.get('JPEG_QUALITY') or 92), 'optimize': True,
                       'progressive': True}
        if exif_bytes:
            save_kwargs['exif'] = exif_bytes
        if comment:
            save_kwargs['comment'] = comment    # the JPEG COM marker
    elif fmt == 'WEBP':
        save_kwargs = {'quality': int(cfg.get('JPEG_QUALITY') or 92)}
        if exif_bytes:
            save_kwargs['exif'] = exif_bytes
    elif fmt == 'PNG':
        if exif_bytes:
            save_kwargs['exif'] = exif_bytes
        if comment:
            from PIL import PngImagePlugin
            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text('Comment', info.comment_text())
            pnginfo.add_text('Description', info.comment_text())
            save_kwargs['pnginfo'] = pnginfo
    if icc:
        save_kwargs['icc_profile'] = icc
    # write next to the target first: if the encoder fails, the source stays intact
    _atomic_put(lambda p: out.save(p, format=fmt, **save_kwargs), out_path)
    return out_path


def write_comment_file(path, info: WatermarkInfo, cfg: dict | None = None, dest=None) -> Path:
    """Write **only** the metadata comment into an already-stored photo.

    The pixels are never touched: the file is re-saved from the very same image
    object, and a JPEG keeps its original quantization tables (``quality='keep'``,
    i.e. no visible re-compression). Used by the CLI's ``--comment-only`` for
    photos that were saved before the metadata feature existed.
    """
    import os

    from PIL import Image, PngImagePlugin
    cfg = cfg or config()
    src = Path(path)
    out_path = Path(dest) if dest else src
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        fmt = (im.format or 'JPEG').upper()
        icc = im.info.get('icc_profile')
        # the pixels stay exactly as they are — so the orientation tag stays too
        exif_bytes, comment = _metadata_block(im, info, cfg, reset_orientation=False)

        save_kwargs = {}
        if fmt in ('JPEG', 'JPG'):
            keep_tables = bool(getattr(im, 'quantization', None))
            save_kwargs = {'optimize': True,
                           'quality': 'keep' if keep_tables
                           else int(cfg.get('JPEG_QUALITY') or 92)}
            if exif_bytes:
                save_kwargs['exif'] = exif_bytes
            if comment:
                save_kwargs['comment'] = comment
        elif fmt == 'PNG':
            if exif_bytes:
                save_kwargs['exif'] = exif_bytes
            if comment:
                pnginfo = PngImagePlugin.PngInfo()
                pnginfo.add_text('Comment', info.comment_text())
                pnginfo.add_text('Description', info.comment_text())
                save_kwargs['pnginfo'] = pnginfo
        elif fmt == 'WEBP':
            if exif_bytes:
                save_kwargs['exif'] = exif_bytes
        else:
            return src
        if icc:
            save_kwargs['icc_profile'] = icc

        _atomic_put(lambda p: im.save(p, format=fmt, **save_kwargs), out_path)
    return out_path


# =========================================================================== #
# the second, simple watermark (v1.14.1) — only «کد رایانه پرونده» as plain text
#
# Owner request: «write a second one (use it) but only write کد رایانه in it
# (simple text no styling and stuff)». The app uses THIS one and activates it
# when the upload is finalized. The code is plain ASCII digits, so the stamp
# never depends on the broken Arabic shaping of the environment.
# =========================================================================== #
def _wm_info_url(info: dict) -> str:
    """The public ``wm_info`` URL encoding every stamped fact (empty → no QR)."""
    from urllib.parse import urlencode

    from django.urls import reverse

    base = str(info.get('base_url') or '').strip().rstrip('/')
    if not base:
        return ''
    try:
        page = reverse('wm_info')
    except Exception:
        return ''
    from app_core.utils.digits import to_en

    # ASCII digits keep the URL short (Persian digits blow up the QR density)
    query = urlencode({
        'code': to_en(str(info.get('code') or '')),
        'case': to_en(str(info.get('case_number') or '')),
        'user': str(info.get('username') or ''),
        'at': to_en(str(info.get('at') or '')),
    })
    return f'{base}{page}?{query}'


def _qr_image(url: str, side: int):
    """A ``side``×``side`` RGBA QR of ``url`` — or ``None`` when anything fails.

    v1.18 — **totally optional**: the ``qrcode`` package may be missing and any
    rendering error must stay invisible to the text watermark.
    """
    if not url or side < 24:
        return None
    try:
        import qrcode
    except Exception:
        # v1.19.1 — never silent: the console/activity log says WHY the QR is
        # missing (the text watermark is stamped regardless, by design).
        logger.warning(
            'qrcode package is not installed — the watermark QR was skipped '
            '(optional). Install it with: pip install "qrcode[pil]"')
        return None
    try:
        qr = qrcode.QRCode(border=1, box_size=6,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        img = img.convert('RGBA')
        return img.resize((side, side))
    except Exception as exc:
        logger.warning('watermark QR could not be rendered (%s) — '
                       'stamping the text watermark only', exc)
        return None


def _shape_text(text: str) -> str:
    """Join/reorder Persian & Arabic letters for Pillow (no libraqm needed).

    v1.20 — Pillow wheels ship without libraqm, so Arabic-script letters print
    as disconnected isolated glyphs (the old «کد رایانه» labels looked garbled
    because of this). The pure-Python ``arabic-reshaper`` + ``python-bidi``
    pair produces presentation forms in visual order, which Pillow draws as
    correctly joined text. Text without Arabic letters passes through
    untouched; any failure falls back to the original string.
    """
    text = str(text or '')
    if not any('\u0600' <= ch <= '\u06ff' and ch.isalpha() for ch in text):
        return text
    try:
        import arabic_reshaper
        try:
            from bidi.algorithm import get_display
        except ImportError:            # python-bidi ≥ 0.6 layout
            from bidi import get_display
        return get_display(arabic_reshaper.reshape(text))
    except Exception:
        return text


def _stamp_lines(info: dict, cfg: dict | None = None) -> list:
    """The stamped lines = the four **values** (+ the optional custom text).

    v1.19 dropped the Persian labels (unshaped letters printed garbled);
    v1.20 appends ``CUSTOM_TEXT`` under the values when it is enabled and
    non-empty (``WATERMARK_CUSTOM_TEXT`` / ``WATERMARK_CUSTOM_TEXT_ENABLED``
    in `.env`).
    """
    lines = [v for v in (info.get('code'), info.get('case_number'),
                         info.get('username'), info.get('at')) if v]
    cfg = cfg if cfg is not None else config()
    if cfg.get('CUSTOM_TEXT_ENABLED', True):
        custom = str(cfg.get('CUSTOM_TEXT') or '').strip()
        if custom:
            lines.append(custom)
    return lines


def simple_overlay(size, code, cfg: dict | None = None):
    """Transparent layer with the watermark values (+ logos + optional QR).

    v1.19 — ``code`` may be a plain string (the code line only, CLI compatible)
    or a dict ``{'code', 'case_number', 'username', 'at', 'base_url'}``.
    The stamp scales with the photo: small photos get a small stamp (never
    taller than ``MAX_HEIGHT_FRACTION`` of the photo), text is drawn at 2× and
    downscaled so it stays crisp, and the QR is skipped when it would be too
    small to scan. The QR sits left of the texts; the two logos sit above them.
    """
    from PIL import Image, ImageDraw

    info = ({'code': str(code).strip(), 'case_number': '', 'username': '',
             'at': '', 'base_url': ''}
            if not isinstance(code, dict) else {
                'code': str(code.get('code') or '').strip(),
                'case_number': str(code.get('case_number') or '').strip(),
                'username': str(code.get('username') or '').strip(),
                'at': str(code.get('at') or '').strip(),
                'base_url': str(code.get('base_url') or '').strip(),
            })
    cfg = {**DEFAULTS, **(cfg or {})}
    width, height = size

    lines = [_shape_text(v) for v in _stamp_lines(info, cfg)]
    if not lines:
        return Image.new('RGBA', size, (0, 0, 0, 0))

    # ---- proportional size: small photo → small stamp --------------------
    # block ≈ 8.1 × font (logos row + gap + 4 lines); cap its height so the
    # stamp never eats the photo (image-1 feedback: shrink on small images).
    max_block = float(cfg.get('MAX_HEIGHT_FRACTION') or 0.38)
    font_size = int(min(width, height) * 0.034)
    font_size = min(font_size, int(height * max_block / 8.1))
    font_size = max(5, min(font_size, 64))

    margin = max(3, int(min(width, height) * float(cfg.get('MARGIN_FRACTION') or 0.022)))
    where = str(cfg.get('SIMPLE_POSITION') or cfg.get('POSITION') or 'bottom-right').lower()
    qr_min_side = int(cfg.get('QR_MIN_SIDE') or 88)

    S = 2  # supersample factor — draw big, downscale: crisp strokes at small sizes

    def render(draw_lines, font):
        """Draw the stamp block at S× resolution on its own small canvas."""
        fs = font_size * S
        line_h = int(fs * 1.45)
        draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))

        # measure the text lines
        line_boxes = []
        for text in draw_lines:
            bbox = draw.textbbox((0, 0), text, font=font)
            if (bbox[2] - bbox[0]) <= 0 or (bbox[3] - bbox[1]) <= 0:
                return None
            line_boxes.append(bbox)
        text_w = max(b[2] - b[0] for b in line_boxes)
        text_h = line_h * len(draw_lines)

        # logos row (above the lines, same right edge)
        logo_h = int(fs * 1.6)
        logos = []
        for rel in cfg.get('LOGOS') or []:
            lg = _logo(_static_dir() / rel, logo_h)
            if lg is not None:
                logos.append(lg)
        gap_logo = int(fs * 0.7) if logos else 0
        logos_w = (sum(lg.width for lg in logos) + 8 * S * (len(logos) - 1)) if logos else 0

        block_w = max(text_w, logos_w)
        block_h = logo_h + gap_logo + text_h

        # draw texts + logos into the (cropped) block canvas, S× resolution
        block = Image.new('RGBA', (block_w, block_h), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(block)
        x_right = block_w
        x = x_right
        for lg in reversed(logos):
            x -= lg.width
            block.alpha_composite(lg, (x, 0))
            x -= 8 * S
        y = logo_h + gap_logo
        stroke = max(1, fs // 14)
        for text, bbox in zip(draw_lines, line_boxes):
            bdraw.text((x_right - (bbox[2] - bbox[0]) - bbox[0], y - bbox[1]),
                       text, font=font, fill=(255, 255, 255, 255),
                       stroke_width=stroke, stroke_fill=(0, 0, 0, 225))
            y += line_h
        return block

    def assemble(block_s):
        """Downscale the S× block to final size, place it + the sharp QR."""
        if block_s is None:
            return None
        out = block_s.resize((max(1, block_s.width // S), max(1, block_s.height // S)),
                             Image.LANCZOS)
        bbox = out.getbbox()
        if bbox is None:
            return out
        block_w = bbox[2] - bbox[0]
        block_h = bbox[3] - bbox[1]
        # optional QR left of the block — only when enabled and big enough
        # to scan; never breaks the texts (_qr_image fails soft + outer catch)
        qr_side = block_h
        qr = None
        if cfg.get('QR_ENABLED', True) and qr_side >= qr_min_side:
            try:
                qr = _qr_image(_wm_info_url(info), qr_side)
            except Exception:
                qr = None
        if qr is not None:
            gap_qr = int(font_size * 1.1)
            left = margin if 'left' in where else width - block_w - gap_qr - qr_side - margin
            top = margin if 'top' in where else height - block_h - margin
            # shift the drawn block right of the QR, then paste the sharp QR
            shifted = Image.new('RGBA', size, (0, 0, 0, 0))
            shifted.alpha_composite(out.crop(bbox), (left + qr_side + gap_qr, top))
            shifted.alpha_composite(qr, (left, top))
            return shifted
        left = margin if 'left' in where else width - block_w - margin
        top = margin if 'top' in where else height - block_h - margin
        shifted = Image.new('RGBA', size, (0, 0, 0, 0))
        shifted.alpha_composite(out.crop(bbox), (left, top))
        return shifted

    stamp_s = render(lines, _font(font_size * S, '700'))
    stamp = assemble(stamp_s) if stamp_s is not None else None
    if stamp is None or stamp.getbbox() is None:
        # v1.17 — a broken TTF must never produce an invisible watermark:
        # fall back to Pillow's bundled font (renders the values fine).
        stamp_s = render(lines, _font_default(font_size * S))
        stamp = assemble(stamp_s) if stamp_s is not None else None
    if stamp is None or stamp.getbbox() is None:
        # last resort: the pure-Latin code value alone (bitmap-font safe).
        stamp_s = render([info['code']], _font_default(font_size * S))
        stamp = assemble(stamp_s) if stamp_s is not None else None
    if stamp is None or stamp.getbbox() is None:
        raise ValueError(f'watermark text did not render: {lines!r}')
    return stamp


def simple_watermark_image(pil_image, code, cfg: dict | None = None):
    """Return a copy of the image carrying only the plain code text."""
    cfg = cfg or config()
    base = pil_image.convert('RGBA')
    out = base.copy()
    out.alpha_composite(simple_overlay(base.size, code, cfg), (0, 0))
    return out


def simple_watermark_file(path, code, cfg: dict | None = None, dest=None) -> Path:
    """Burn the plain «کد رایانه» text into the photo (in place, or into ``dest``).

    Same safety as :func:`watermark_file`: written to a temporary neighbour and
    only then moved into place. No metadata, no styling — just the text.
    """
    import os

    from PIL import Image, ImageOps

    cfg = cfg or config()
    src = Path(path)
    out_path = Path(dest) if dest else src
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(src) as im:
        fmt = (im.format or 'JPEG').upper()
        icc = im.info.get('icc_profile')
        image = ImageOps.exif_transpose(im.convert('RGBA'))
        if image is None:
            image = im.convert('RGBA')
    out = simple_watermark_image(image, code, cfg)
    save_kwargs = {}
    if cfg.get('DEGRADED_SAVE'):
        if fmt in ('JPEG', 'JPG'):
            out = out.convert('RGB')
        save_kwargs = {}
    elif fmt in ('JPEG', 'JPG'):
        out = out.convert('RGB')
        # v1.19 — quality 95 + subsampling 0 (4:4:4): the re-encode must not
        # soften the photo the way the old 4:2:0 default did.
        save_kwargs = {'quality': int(cfg.get('JPEG_QUALITY') or 95),
                       'subsampling': 0, 'optimize': True, 'progressive': True}
    elif fmt == 'WEBP':
        save_kwargs = {'quality': int(cfg.get('JPEG_QUALITY') or 95)}
    if icc and not cfg.get('DEGRADED_SAVE'):
        save_kwargs['icc_profile'] = icc
    _atomic_put(lambda p: out.save(p, format=fmt, **save_kwargs), out_path)
    return out_path


def run_simple_for_submission(submission, base_url: str | None = None) -> int:
    """The watermark program of the app (v1.18) — runs **at finalization**.

    Stamps every photo of the case (مقصر + زیان‌دیده‌ها) with the watermark
    texts («کد رایانه / شماره پرونده / نام کاربری / تاریخ و ساعت» + logos) and
    marks each row ``watermarked_at``. Returns the number of stamped photos.
    Never raises. ``base_url`` (when given) enables the optional QR code.
    """
    from django.utils import timezone as tz

    from app_media.services import formats, storage

    record = getattr(submission, 'any_record', None)
    code = (getattr(submission, 'entered_file_code', '')
            or (getattr(record, 'computer_code', '') if record else '')) or ''
    if not str(code).strip():
        return 0
    try:
        from app_core.templatetags.jalali_tags import jalali_datetime_of
        at = jalali_datetime_of(tz.now())
    except Exception:
        at = tz.now().strftime('%Y-%m-%d %H:%M')
    info = {
        'code': str(code).strip(),
        'case_number': str(getattr(record, 'case_number', '') or ''),
        'username': (getattr(submission, 'completed_username', '')
                     or getattr(submission, 'auth_username', '') or ''),
        'at': at,
        'base_url': base_url or getattr(settings, 'PUBLIC_BASE_URL', '') or '',
    }
    cfg = config()
    count = 0
    problems = []
    for image in submission.images.all():
        path = storage.root() / image.image_path
        if not path.exists():
            problems.append(f'{image.image_path}: فایل روی دیسک نیست')
            continue
        if formats.needs_no_watermark(path.name):
            # v1.21 — HEIC/HEIF/DNG are stored byte-for-byte: Pillow can neither
            # open nor write them, and a conversion is explicitly unwanted, so
            # these photos keep their original bytes (no stamp, no error).
            continue
        try:
            simple_watermark_file(path, info, cfg)
        except Exception:
            # v1.17 — retry once with a degraded save (no icc/progressive),
            # then record the problem instead of silently leaving a photo
            # without the watermark.
            try:
                simple_watermark_file(path, info, {**cfg, 'DEGRADED_SAVE': True})
            except Exception as exc:
                problems.append(f'{image.image_path}: {exc}')
                continue
        try:
            image.watermarked_at = tz.now()
            image.size_bytes = path.stat().st_size
            image.save(update_fields=['watermarked_at', 'size_bytes'])
        except Exception:
            pass
        count += 1

    # v1.15 — never leave a staging/scratch duplicate in the case folder:
    # after finalizing and watermarking only the stamped photos may remain
    try:
        for stray in storage.case_dir(submission).rglob('*'):
            if stray.is_file() and (stray.name.endswith('.wm-tmp')
                                    or stray.name.endswith('.upload')):
                try:
                    stray.unlink()
                except OSError:
                    pass
    except Exception:
        pass

    # v1.17 — stamping must never fail silently (owner: the watermark has to
    # be on EVERY image); any problem is recorded in the activity log.
    if problems:
        try:
            from app_account.activity import log_activity
            log_activity('watermark_problem', request=None, method='POST',
                         username=submission.auth_username or '',
                         description='مشکل واترمارک: ' + '؛ '.join(problems[:5]),
                         object_label=getattr(submission, 'unique_number', '') or '')
        except Exception:
            pass
    return count


# =========================================================================== #
# the script (replaces watermark.sh + manage.py watermark_images)
# =========================================================================== #
def _out(text=''):
    """Print without blowing up on a console that cannot encode Persian."""
    try:
        print(text)
    except UnicodeEncodeError:                                   # pragma: no cover
        sys.stdout.write(text.encode('ascii', 'replace').decode('ascii') + '\n')


def _cli_collect(options):
    """The list of CaseImage rows to stamp (or an ad-hoc rows for --path)."""
    from app_media.models import CaseImage

    if options.get('path'):
        return _cli_from_path(options['path'])

    qs = CaseImage.objects.select_related('submission', 'submission__record',
                                          'submission__record_third')
    if options.get('case'):
        key = str(options['case']).strip()
        qs = qs.filter(models_case_q(key))
    if options.get('section'):
        qs = qs.filter(section=options['section'])
    if not options.get('all') and not options.get('force'):
        qs = qs.filter(watermarked_at__isnull=True)
    return list(qs.order_by('submission_id', 'uploaded_at'))


def _cli_from_path(raw):
    """Files on disk (no DB row needed) — matched to a row when possible."""
    base = Path(settings.STORAGE_ROOT)
    raw_path = Path(raw)
    candidates = ([raw_path] if raw_path.is_absolute()
                  else [Path(settings.BASE_DIR) / raw_path, base / raw_path])
    target = next((c for c in candidates if c.exists()), None)
    if target is None:
        raise SystemExit('مسیر پیدا نشد: ' + ' یا '.join(str(c) for c in candidates))
    files = [target] if target.is_file() else sorted(
        p for p in target.rglob('*') if p.is_file() and is_image_name(p))
    from app_media.models import CaseImage
    rows = {i.image_path: i for i in CaseImage.objects.select_related(
        'submission', 'submission__record', 'submission__record_third')}
    out = []
    for path in files:
        rel = str(path.resolve().relative_to(base.resolve())).replace('\\', '/')
        row = rows.get(rel)
        if row is None:
            row = CaseImage(image_path=rel, original_name=path.name, section='')
            row.submission = None
            # no database row: the file's own timestamp becomes «تاریخ و ساعت»
            try:
                from datetime import datetime as _dt, timezone as _tz
                row.uploaded_at = _dt.fromtimestamp(path.stat().st_mtime, tz=_tz.utc)
            except OSError:
                pass
        out.append(row)
    return out


def models_case_q(key):
    """Q object matching a case by unique number or entered computer code."""
    from django.db.models import Q
    return (Q(submission__unique_number=key) | Q(submission__entered_file_code=key)
            | Q(submission__record__computer_code=key)
            | Q(submission__record_third__computer_code=key))


def main(argv=None):
    """``python -m app_media.services.watermark …`` — re-stamp photos on disk."""
    import argparse
    import os

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'dana.settings')
    import django
    django.setup()

    from django.core.management.base import CommandError

    parser = argparse.ArgumentParser(
        prog='watermark',
        description='درج واترمارک (لوگوها + تاریخ و ساعت و مشخصات پرونده) روی تصاویر ذخیره‌شده')
    parser.add_argument('--all', action='store_true',
                        help='همهٔ تصاویر همهٔ پرونده‌ها (نه فقط درج‌نشده‌ها)')
    parser.add_argument('--case', default='', metavar='CODE',
                        help='فقط تصاویر یک پرونده (شمارهٔ یکتا یا کد رایانه پرونده)')
    parser.add_argument('--section', default='', metavar='KEY',
                        help='فقط یک فیلد (car_card_front، license_back، car_shots، …)')
    parser.add_argument('--path', default='', metavar='PATH',
                        help='یک فایل یا پوشه روی دیسک (storage/…) به‌جای پایگاه داده')
    parser.add_argument('--force', action='store_true',
                        help='تصاویری که قبلاً واترمارک شده‌اند را هم دوباره درج کن '
                             '(هشدار: مُهر روی مُهر قبلی کشیده می‌شود)')
    parser.add_argument('--out', default='', metavar='DIR',
                        help='نوشتن نسخه‌های واترمارک‌شده در این پوشه (به‌جای بازنویسی)')
    parser.add_argument('--comment-only', action='store_true',
                        help='فقط متن مشخصات را در متادیتای تصویر بنویس (واترمارک دوباره '
                             'کشیده نمی‌شود)')
    parser.add_argument('--simple', action='store_true',
                        help='واترمارک ساده (v1.14.1): فقط «کد رایانه پرونده» به‌صورت متن '
                             'ساده — همان‌چیزی که هنگام نهایی شدن آپلود اجرا می‌شود')
    parser.add_argument('--dry-run', action='store_true',
                        help='فقط گزارش بده، هیچ فایلی را تغییر نده')
    parser.add_argument('--limit', type=int, default=0,
                        help='حداکثر تعداد تصویر (۰ = بی‌نهایت)')
    options = vars(parser.parse_args(argv))

    cfg = config()

    # environment preflight — say *why* nothing can be stamped instead of
    # silently doing nothing
    problems = preflight()
    if problems and options.get('simple'):
        problems = [x for x in problems if 'raqm' not in x and 'شکل' not in x]
    if problems:
        _out('⚠️  محیط برای درج واترمارک آماده نیست:')
        for line in problems:
            _out('   • ' + line)
        if not options['dry_run']:
            raise SystemExit('ابتدا موارد بالا را برطرف کنید.')

    if not cfg.get('ENABLED', True) and not options['force']:
        _out('⚠️  واترمارک در تنظیمات غیرفعال است (WATERMARK["ENABLED"] = False).')
        _out('    برای اجرای دستی همین حالا از --force استفاده کنید.')

    out_dir = Path(options['out']).resolve() if options['out'] else None
    dry = options['dry_run']
    targets = _cli_collect(options)
    if options['limit']:
        targets = targets[:options['limit']]

    if not targets:
        _out('هیچ تصویری برای واترمارک پیدا نشد.')
        _out('   • همهٔ تصاویر قبلاً واترمارک شده‌اند → برای درج دوباره از --all --out استفاده کنید.')
        _out('   • برای بررسی یک پوشه روی دیسک → --path storage/files --out D:\\stamped')
        return 0

    _out(f'واترمارک — {to_fa(len(targets))} تصویر'
         + (' (اجرای آزمایشی، بدون تغییر)' if dry else '')
         + (f' → {out_dir}' if out_dir else ''))
    _out('─' * 72)

    done = skipped = failed = 0
    for image in targets:
        rel = image.image_path
        src = Path(settings.STORAGE_ROOT) / rel
        if not src.exists():
            _out(f'✗ {rel} — فایل روی دیسک نیست')
            failed += 1
            continue

        # ---- what has to happen to this file? ---------------------------
        already = bool(image.watermarked_at)
        comment_only = options['comment_only']
        want_render = bool(out_dir) or not already or options['force']
        want_comment = comment_only and already and not out_dir
        if not (want_render or want_comment):
            skipped += 1
            continue

        submission = getattr(image, 'submission', None) if image.pk else None
        label = (f'{getattr(submission, "auth_username", "") or "—"} · '
                 f'{image.section or "فایل روی دیسک"}')
        info = WatermarkInfo.from_image(image, submission=submission)

        dest = None
        if out_dir:
            dest = out_dir / src.name
            counter = 1
            while dest.exists():
                counter += 1
                dest = out_dir / f'{src.stem}-{counter}{src.suffix}'

        if dry:
            what = ('فقط متن مشخصات' if want_comment
                    else ('واترمارک ساده (کد رایانه)' if options['simple']
                          else 'واترمارک + مشخصات'))
            _out(f'• {rel}  [{label}]  ({what})')
            done += 1
            continue

        try:
            if want_comment:               # metadata only — pixels untouched
                write_comment_file(src, info, cfg)
            elif options['simple']:        # the second, plain stamp
                simple_watermark_file(src, info.computer_code, cfg, dest=dest)
            else:
                watermark_file(src, info, cfg, dest=dest)
        except Exception as exc:                          # keep going
            _out(f'✗ {rel} — خطا: {exc}')
            failed += 1
            continue

        if not out_dir and image.pk:
            updates = ['size_bytes']
            if want_render and not comment_only:
                image.watermarked_at = timezone.now()
                updates.append('watermarked_at')
            image.size_bytes = Path(settings.STORAGE_ROOT, image.image_path).stat().st_size
            image.save(update_fields=list(set(updates)))

        done += 1
        details = ('  (فقط متن مشخصات)' if want_comment and not want_render
                   else f'  {info.when_text()}')
        if out_dir:
            details += f'  → {dest.name}'
        _out(f'✓ {rel}  [{label}]{details}')

    _out('─' * 72)
    _out(f'انجام‌شده: {to_fa(done)} | رد‌شده (قبلاً واترمارک‌شده): {to_fa(skipped)}'
         f' | ناموفق: {to_fa(failed)}')
    return 0


if __name__ == '__main__':                                # pragma: no cover
    raise SystemExit(main())
