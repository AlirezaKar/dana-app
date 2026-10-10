"""Accepted upload formats (v1.21).

Only the formats a phone camera really produces are accepted — **HEIF/HEIC,
JPEG/JPG, PNG and RAW/DNG (Apple ProRAW included, it is a DNG)**. Nothing else
may be uploaded and nothing is ever converted: the file is stored byte-for-byte
under the extension it was taken with.

The check is done twice on purpose:

* the ``accept`` attribute of the file inputs (:data:`ACCEPT_ATTR`) narrows the
  phone's picker — a hint only, every browser lets the user override it;
* :func:`validate` is the real gate: the **extension** must be one of the
  allowed ones *and* the **content** must be that same format (a renamed
  ``.webp``/``.gif``/``.bmp`` never gets through).

Content is recognised by its magic bytes — Pillow is deliberately not used for
this: it cannot open HEIC at all (no ``pillow-heif`` on a stock install) and
opening a 40 MB ProRAW just to look at its header would be a waste.
"""
from pathlib import Path

#: extension → format family
ALLOWED = {
    '.jpg': 'jpeg',
    '.jpeg': 'jpeg',
    '.png': 'png',
    '.heic': 'heif',
    '.heif': 'heif',
    '.dng': 'dng',
}

#: family → the extension used when the upload carries none (a phone browser
#: sometimes sends the file simply as ``image``)
CANONICAL = {'jpeg': '.jpg', 'png': '.png', 'heif': '.heic', 'dng': '.dng'}

#: mime type per family — for serving the stored file back to the browser
MIME = {
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'heif': 'image/heic',
    'dng': 'image/x-adobe-dng',
}

#: value of the ``accept`` attribute of every upload input
ACCEPT_ATTR = ('.jpg,.jpeg,.png,.heic,.heif,.dng,'
               'image/jpeg,image/png,image/heic,image/heif,image/x-adobe-dng')

#: human-readable list for the error message (static text — edit freely)
ALLOWED_LABEL = 'JPG/JPEG، PNG، HEIC/HEIF و DNG (RAW)'

#: formats Pillow can neither open nor write → they are stored untouched and the
#: watermark step skips them instead of failing (no conversion, ever).
NO_WATERMARK = {'.heic', '.heif', '.dng'}

#: ISO-BMFF brands that mean «HEIF family» (iPhone photos are heic/heix)
_HEIF_BRANDS = {b'heic', b'heix', b'hevc', b'hevx', b'heim', b'heis',
                b'hevm', b'hevs', b'mif1', b'msf1'}

#: DNG writes its version tag (0xC612) into IFD0 — used to tell a real DNG from
#: an ordinary TIFF that only shares the header.
_DNG_TAG_LE = b'\x12\xc6'
_DNG_TAG_BE = b'\xc6\x12'


def sniff(head: bytes):
    """The format family of the first bytes of a file, or ``None``."""
    if not head:
        return None
    if head[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    if head[:8] == b'\x89PNG\r\n\x1a\n':
        return 'png'
    if head[4:8] == b'ftyp' and head[8:12] in _HEIF_BRANDS:
        return 'heif'
    if head[:4] in (b'II*\x00', b'MM\x00*'):
        # a TIFF header alone is not enough — it has to be a DNG
        if _DNG_TAG_LE in head[:65536] or _DNG_TAG_BE in head[:65536]:
            return 'dng'
        return None
    return None


def extension_of(filename):
    """Lower-case extension of a file name ('' when there is none).

    A bare extension (``'.heic'``) is accepted as it is — ``Path('.heic')``
    would read it as a *hidden file name* without a suffix.
    """
    name = str(filename or '')
    if name.startswith('.') and '/' not in name and '\\' not in name:
        return name.lower()
    return Path(name).suffix.lower()


def family_of(filename):
    """The allowed family an extension stands for (``None`` = not allowed)."""
    return ALLOWED.get(extension_of(filename))


def is_allowed(filename):
    return family_of(filename) is not None


def is_allowed_suffix(suffix):
    """True when an extension (``.jpg`` / ``jpg``) is one of the allowed ones."""
    suffix = str(suffix or '').lower()
    if suffix and not suffix.startswith('.'):
        suffix = '.' + suffix
    return suffix in ALLOWED


def validate(uploaded_file, head: bytes | None = None):
    """Check one upload. Returns ``(ok, error, suffix)``.

    ``suffix`` is the extension the file must be stored under: the one it came
    with when that one is allowed, otherwise the canonical extension of the
    format its content was recognised as.
    """
    name = getattr(uploaded_file, 'name', '') or ''
    ext = extension_of(name)
    family = ALLOWED.get(ext)

    if head is None:
        head = _read_head(uploaded_file)
    found = sniff(head)

    if family is not None:
        if found is None:
            return False, 'محتوای فایل با پسوند آن همخوانی ندارد؛ فایل تصویر معتبر نیست.', ext
        if found != family:
            return False, (f'محتوای فایل {found.upper()} است اما پسوند آن '
                           f'{ext or "—"} می‌باشد. فقط {ALLOWED_LABEL} پذیرفته می‌شود.'), ext
        return True, '', ext

    # no (allowed) extension → the content decides, but only inside the list
    if found is None:
        return False, (f'قالب فایل پذیرفته نیست. فقط {ALLOWED_LABEL} مجاز است.'), ext
    return True, '', CANONICAL[found]


def _read_head(uploaded_file, size: int = 65536) -> bytes:
    """The first ``size`` bytes of an upload, leaving the file ready to read."""
    try:
        head = uploaded_file.read(size)
    except Exception:
        return b''
    try:
        uploaded_file.seek(0)
    except Exception:
        pass
    return head or b''


def mime_for(path_or_name):
    """Mime type of a stored photo (browser-displayable ones first)."""
    return MIME.get(family_of(path_or_name), '')


def needs_no_watermark(path_or_name) -> bool:
    """True for the formats that must stay byte-for-byte (HEIC/DNG)."""
    return extension_of(path_or_name) in NO_WATERMARK
