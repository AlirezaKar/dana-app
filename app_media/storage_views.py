"""Storage browser (v1.7) — a labeled, read-only window into the `storage/` area.

The small «مشاهدهٔ پوشهٔ ذخیره‌سازی» button next to the badges of the **نوع بیمه**
page (stage 2) opens ``/media/storage/`` in a new tab:

    /media/storage/                       فهرست پرونده‌های پایان‌یافته
    /media/storage/folder/<path>/         جزئیات یک پوشه (پوشه‌های داخلی + فایل‌ها)
    /media/storage/raw/<path>             نمایش/دانلود یک فایل

Every folder on a page is rendered as a link button that opens **its own detail
page**; every image is shown as a thumbnail (served through ``storage_raw``) and
every name is printed next to it.

Rules
-----
* Browsing is read-only; the explicit POST watermark action overwrites images;
* every requested path is resolved and clamped to ``STORAGE_ROOT``; a path that
  escapes the root (``..``) or does not exist is a 404;
* access needs the app session (the same login as the wizard) or a staff account;
* numbers/dates are printed with Persian digits and Jalali timestamps.
"""
from datetime import datetime
from datetime import timezone as dt_timezone
from functools import wraps
from pathlib import Path

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.utils import timezone as dj_timezone
from django.views.decorators.http import require_POST

from app_core.utils.digits import to_fa
from app_core.utils.jalali import gregorian_to_jalali_str
from app_media.constants import TITLE_BY_KEY

from .services import storage

IMAGE_SUFFIXES = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tif', '.tiff'}
#: well-known folder names get their own Persian label (v1.21 — «tmp» is gone:
#: there are no temporary folders any more)
FOLDER_LABELS = {}
#: never listed (system noise)
SKIP_NAMES = {'.DS_Store', 'Thumbs.db', '.gitkeep'}


# ---------------------------------------------------------------- helpers ----
def _allowed(request) -> bool:
    """The app session (wizard login) or a Django staff account may look around."""
    if (request.session.get('auth') or {}).get('username'):
        return True
    user = getattr(request, 'user', None)
    return bool(user is not None and getattr(user, 'is_authenticated', False)
                and getattr(user, 'is_staff', False))


def _session_username(request) -> str:
    return ((request.session.get('auth') or {}).get('username') or '').strip()


def _owned_case_folder(folder: Path, username: str) -> bool:
    """v1.14 — a case folder belongs to the logged-in user when its name
    **ends with their username** (``<کد رایانه>-<username>``).

    The second line of defence is the database: when a ثبت پرونده for this
    folder exists, its «ثبت‌کننده» must be the same user. Staff members that
    browse without an app session (``username == ''``) see everything.
    """
    name = folder.name
    if not username:
        return True
    if not name.endswith('-' + username):
        return False
    code = name[: -(len(username) + 1)]
    if not code:
        return False
    from django.db.models import Q

    from app_main.models import CaseSubmission
    sub = (CaseSubmission.objects
           .filter(auth_username__iexact=username)
           .filter(Q(entered_file_code=code) | Q(record__computer_code=code)
                   | Q(record_third__computer_code=code))
           .first())
    if sub is not None and (sub.completed_username or sub.auth_username).lower() != username.lower():
        return False
    return True


def _access_required(view):
    """Only the wizard session (or a staff account) may browse the storage area."""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not _allowed(request):
            return redirect('login')
        return view(request, *args, **kwargs)
    return wrapper


def _root() -> Path:
    return storage.root().resolve()


def _case_folder_of(path: Path):
    """The case folder (``files/<date>/<کد رایانه>-<username>``) a path lives in.

    Returns ``(case_folder, depth)`` or ``(None, 0)`` — ``depth`` counts the
    levels of ``path`` below the case folder (0 = the folder itself).
    """
    root = _root()
    try:
        rel = path.resolve().relative_to(root)
    except ValueError:
        return None, 0
    parts = rel.parts
    if len(parts) < 2 or parts[0] != 'files':
        return None, 0
    if len(parts) == 2:                      # files/<date> — not a case folder
        return None, 0
    case = root / 'files' / parts[1] / parts[2]
    return case, len(parts) - 3


def _resolve(subpath='') -> Path:
    """Absolute path inside the storage root — anything else is a 404."""
    root = _root()
    clean = (subpath or '').strip().strip('/')
    target = (root / clean).resolve() if clean else root
    if target != root and root not in target.parents:
        raise Http404('outside the storage root')
    if not target.exists():
        raise Http404('not found')
    return target


def _require_owned(request, path: Path):
    """v1.14 — a case folder is only visible to the user it ends with."""
    case, _depth = _case_folder_of(path)
    if case is not None and not _owned_case_folder(case, _session_username(request)):
        raise Http404('not your case folder')


def _rel(path: Path) -> str:
    """POSIX-style path relative to the storage root (URL friendly)."""
    return path.resolve().relative_to(_root()).as_posix()


def _label_for(name: str) -> str:
    """Persian label of a well-known folder (`tmp`, upload sections) else ''."""
    return FOLDER_LABELS.get(name) or TITLE_BY_KEY.get(name, '')


def human_size(num_bytes) -> str:
    """12345 -> '۱۲٫۱ کیلوبایت' (Persian digits, one decimal)."""
    size = float(num_bytes or 0)
    for unit, divider in (('گیگابایت', 1024 ** 3), ('مگابایت', 1024 ** 2), ('کیلوبایت', 1024)):
        if size >= divider:
            return to_fa(f'{size / divider:.1f}').replace('.', '٫') + f' {unit}'
    return to_fa(f'{int(size)}') + ' بایت'


def _jalali_time(ts: float) -> str:
    dt = dj_timezone.localtime(datetime.fromtimestamp(ts, tz=dt_timezone.utc))
    date = gregorian_to_jalali_str(dt.year, dt.month, dt.day)
    return to_fa(f'{date} {dt.strftime("%H:%M")}')


def _is_image(path: Path) -> bool:
    """True for image files — by extension, or by content when there is none."""
    if path.suffix.lower() in IMAGE_SUFFIXES:
        return True
    if path.suffix or path.stat().st_size > 40 * 1024 * 1024:
        return False
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            img.verify()
        return True
    except Exception:
        return False


def _image_dimensions(path: Path):
    """(width, height) of an image file, or None — never raises."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            return img.size
    except Exception:
        return None


def _children(folder: Path):
    try:
        entries = sorted(folder.iterdir(), key=lambda p: (p.is_file(), p.name))
    except OSError:
        return []
    return [p for p in entries if p.name not in SKIP_NAMES and not p.name.startswith('~$')]


def _walk_files(folder: Path):
    """All files below `folder` (recursive), skipping system noise."""
    out = []
    for path in folder.rglob('*'):
        if path.is_file() and path.name not in SKIP_NAMES and not path.name.startswith('~$'):
            out.append(path)
    return sorted(out, key=lambda p: str(p).lower())


def _sniff_type(path: Path):
    """Mime type from the file content (used when the name carries no extension)."""
    try:
        from PIL import Image as PILImage
        with PILImage.open(path) as img:
            return PILImage.MIME.get(img.format)
    except Exception:
        return None


def _file_entry(path: Path):
    st = path.stat()
    is_image = _is_image(path)
    dims = _image_dimensions(path) if is_image else None
    return {
        'name': path.name,
        'rel': _rel(path),
        'parent': path.parent.name,
        'parent_label': _label_for(path.parent.name),
        'size': st.st_size,
        'size_label': human_size(st.st_size),
        'modified': _jalali_time(st.st_mtime),
        'is_image': is_image,
        'dims': f'{to_fa(dims[0])}×{to_fa(dims[1])}' if dims else '',
        'ext': (path.suffix.lstrip('.') or ('IMG' if is_image else '؟')).upper(),
    }


def _folder_entry(path: Path):
    files = _walk_files(path)
    total = sum(f.stat().st_size for f in files)
    mtime = max([p.stat().st_mtime for p in [path] + files] or [path.stat().st_mtime])
    previews = [_file_entry(f) for f in files if _is_image(f)][:6]
    return {
        'name': path.name,
        'rel': _rel(path),
        'label': _label_for(path.name),
        'file_count': len(files),
        'file_count_label': f'{to_fa(len(files))} فایل',
        'size_label': human_size(total),
        'modified': _jalali_time(mtime),
        'subfolders': sum(1 for p in _children(path) if p.is_dir()),
        'previews': previews,
        'extra_previews': max(0, len([f for f in files if _is_image(f)]) - len(previews)),
    }


def _listing(folder: Path):
    """(subfolders, files) of one folder — both as ready-to-render dicts."""
    folders, files = [], []
    for entry in _children(folder):
        if entry.is_dir():
            folders.append(_folder_entry(entry))
        elif entry.is_file():
            files.append(_file_entry(entry))
    return folders, files


def _crumbs(subpath: str):
    """Breadcrumb of the current path: [(label, url_or_None), …]."""
    crumbs = [{'label': 'ریشهٔ ذخیره‌سازی', 'rel': '',
               'url': None if not subpath else _folder_url('')}]
    parts = [p for p in str(subpath or '').split('/') if p]
    walked = []
    for part in parts:
        walked.append(part)
        rel = '/'.join(walked)
        crumbs.append({'label': _label_for(part) or part, 'rel': rel,
                       'url': None if rel == subpath.strip('/') else _folder_url(rel)})
    return crumbs if subpath else [{'label': 'ریشهٔ ذخیره‌سازی', 'rel': '', 'url': None}]


def _folder_url(subpath: str) -> str:
    from django.urls import reverse
    subpath = str(subpath or '').strip('/')
    return reverse('storage_folder', args=[subpath]) if subpath else reverse('storage_index')


def _raw_url(subpath: str) -> str:
    from django.urls import reverse
    return reverse('storage_raw', args=[str(subpath).strip('/')])


# ------------------------------------------------------------------ views ----
@_access_required
def storage_index(request):
    """Content of ``storage/files`` — the case folders of the logged-in user.

    v1.21 — the «پوشه‌های موقت» (``storage/tmp``) section is gone: every photo is
    written straight into its final case folder, so there is nothing temporary
    left to list (owner request).
    """
    root = _root()
    username = _session_username(request)

    # the finished cases live in ``storage/files/<date>/<کد رایانه>-<username>``
    # (v1.14); only the folders that **end with the logged-in username** are
    # listed — everyone else's work is invisible here
    files_root = root / 'files'
    final_cases = []
    if files_root.is_dir():
        for date_dir in _children(files_root):
            if not date_dir.is_dir():
                continue
            for d in _children(date_dir):
                if d.is_dir() and _owned_case_folder(d, username):
                    entry = _folder_entry(d)
                    entry['name'] = f'{date_dir.name}/{d.name}'
                    final_cases.append(entry)
    final_count = sum(f['file_count'] for f in final_cases) if final_cases else 0

    # legacy case folders directly under storage/ (before the date layout)
    final_folders = []
    for d in _children(root):
        if d.is_dir() and d.name not in ('tmp', 'data', 'files') and _owned_case_folder(d, username):
            final_folders.append(_folder_entry(d))

    data_files = [_file_entry(f) for f in _children(root / 'data')] if (root / 'data').is_dir() else []

    case_files = [f for entry in final_cases for f in _walk_files(root / entry['rel'])]
    total_size = sum(f.stat().st_size for f in case_files)
    newest = max([f.stat().st_mtime for f in case_files], default=None)
    return render(request, 'media/storage_index.html', {
        'summary': {
            'folders': len(final_cases) + len(final_folders),
            'files': len(case_files),
            'size': human_size(total_size),
            'newest': _jalali_time(newest) if newest else '—',
        },
        'final_folders': final_folders,
        'final_cases': final_cases,
        'files_root': str(files_root),
        'files_summary': {'folders': len(final_cases), 'files': final_count},
        'data_files': data_files,
        'root_path': str(root),
        'crumbs': _crumbs(''),
        'folder_url': _folder_url,
        'raw_url': _raw_url,
    })


@_access_required
def storage_folder(request, subpath=''):
    """Detail of one folder: its subfolders (as link buttons) and its files."""
    subpath = str(subpath or '').strip('/')
    folder = _resolve(subpath)
    _require_owned(request, folder)
    if not folder.is_dir():
        raise Http404('not a folder')
    folders, files = _listing(folder)
    inside = subpath.split('/') if subpath else []
    # v1.14 — a date folder only lists the case folders that end with the
    # logged-in username
    if len(inside) == 2 and inside[0] == 'files':
        username = _session_username(request)
        folders = [f for f in folders
                   if _owned_case_folder(folder / f['name'], username)]
    total_size = sum(f.stat().st_size for f in _walk_files(folder))
    return render(request, 'media/storage_folder.html', {
        'can_stamp': _can_stamp(request, folder),
        'folder_name': folder.name or 'storage',
        'folder_label': _label_for(folder.name),
        'abs_path': str(folder),
        'subpath': subpath,
        'folders': folders,
        'files': files,
        'summary': {
            'folders': len(folders),
            'files': len(files),
            'size': human_size(total_size),
            'modified': _jalali_time(folder.stat().st_mtime),
        },
        'parent_url': _folder_url('/'.join(inside[:-1])) if inside else None,
        'index_url': _folder_url(''),
        'crumbs': _crumbs(subpath),
        'folder_url': _folder_url,
        'raw_url': _raw_url,
    })


@_access_required
def storage_raw(request, subpath=''):
    """Serve one file from the storage area (inline) — path-clamped."""
    path = _resolve(subpath)
    _require_owned(request, path)
    if not path.is_file():
        raise Http404('not a file')
    import mimetypes
    ctype = mimetypes.guess_type(path.name)[0]
    if not ctype or ctype == 'application/octet-stream':
        ctype = _sniff_type(path) or ctype or 'application/octet-stream'
    resp = FileResponse(open(path, 'rb'), content_type=ctype)
    resp['Content-Disposition'] = f'inline; filename="{path.name}"'
    return resp


def _can_stamp(request, folder):
    # App users may mutate only their own case tree, never a shared ancestor.
    if not _session_username(request):
        return _allowed(request)
    case, _ = _case_folder_of(folder)
    return case is not None and _owned_case_folder(case, _session_username(request))


@_access_required
@require_POST
def storage_watermark(request, subpath=''):
    """Manual-only, CSRF-protected folder stamp with post/redirect/get."""
    folder = _resolve(subpath)
    _require_owned(request, folder)
    if not folder.is_dir() or not _can_stamp(request, folder):
        raise Http404('not an owned case folder')
    if request.POST.get('confirm') != 'stamp':
        messages.error(request, 'برای بازنویسی تصاویر ابتدا تأیید کنید.')
        return redirect('storage_folder', subpath=subpath)
    from .services.watermark import run_manual_for_folder

    result = run_manual_for_folder(
        folder, authorize=lambda path: _require_owned(request, path),
        base_url=request.build_absolute_uri('/'))
    text = (f"واترمارک دستی: {to_fa(result['done'])} تصویر ذخیره شد؛ "
            f"{to_fa(result['skipped'])} فایل رد شد؛ "
            f"{to_fa(result['failed'])} خطا.")
    (messages.warning if result['failed'] else messages.success)(request, text)
    return redirect('storage_folder', subpath=subpath)
