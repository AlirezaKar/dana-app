"""Upload-section constants (spec.md C5, v1.14 owner layout).

Every party of the case («مقصر» = the submission itself, each «زیان‌دیده» =
one :class:`app_main.DamagedParty`) uploads the same **three groups** of
fields; each field takes one or more photos and every photo is stored under
the name of its field (``car_card_front.jpg``, ``license_back.jpg``, …).

G1 — «پشت و رو گواهینامه و کارت ماشین»
    license_front / license_back / car_card_front / car_card_back
    bulk taking, **no timer**; a confirm button at the end of the group that
    may be pressed again and again (no one-time limitation).

G2 — «شماره شاسی و پلاک‌ها»
    chassis_number / plate_front / plate_back
    bulk taking **with the timer rule** (the same CAR_IMAGE_MAX_GAP_SECONDS as
    every other part) over the whole group; its confirm is **one-time**.

G3 — «اطراف ماشین»
    car_shots — around-the-car photos (پشت / جلو / راست / چپ), timed, one-time
    confirm (the v1.4 behaviour, minus شماره شاسی which moved to G2).
"""
from django.conf import settings

SECTION_CHOICES = [
    ('license_front', 'روی گواهینامه'),
    ('license_back', 'پشت گواهینامه'),
    ('car_card_front', 'روی کارت ماشین'),
    ('car_card_back', 'پشت کارت ماشین'),
    ('chassis_number', 'شماره شاسی'),
    ('plate_front', 'پلاک جلو'),
    ('plate_back', 'پلاک پشت'),
    ('car_shots', 'عکس‌های اطراف ماشین'),
]
SECTION_KEYS = [k for k, _ in SECTION_CHOICES]
TITLE_BY_KEY = dict(SECTION_CHOICES)

# v1.15 — every document field holds exactly ONE photo: uploading the field
# again replaces the previous file (no «-2» duplicates on disk). Only
# «عکس‌های اطراف ماشین» is a multi-photo field (4 …).
MULTI_PHOTO_SECTIONS = {'car_shots'}

#: v1.21 — the fields that take a single photo (the complement of the multi
#: ones). Their upload buttons disappear as soon as the field has its photo and
#: come back when that photo is deleted; a second upload is refused.
SINGLE_PHOTO_SECTIONS = {k for k, _ in SECTION_CHOICES if k not in MULTI_PHOTO_SECTIONS}

# minimum images per field (None = unlimited)
SECTION_MIN = {
    'license_front': 1,
    'license_back': 1,
    'car_card_front': 1,
    'car_card_back': 1,
    'chassis_number': 1,
    'plate_front': 1,
    'plate_back': 1,
    'car_shots': 4,
}
# maximum images per field (None = unlimited — bulk taking)
SECTION_MAX = {
    'license_front': None,
    'license_back': None,
    'car_card_front': None,
    'car_card_back': None,
    'chassis_number': None,
    'plate_front': None,
    'plate_back': None,
    'car_shots': None,
}

# --------------------------------------------------------------------------- #
# the three upload groups (identical for مقصر and every زیان‌دیده)
# --------------------------------------------------------------------------- #
GROUP_DOCS = 'group_docs'        # no timer, confirm repeatable
GROUP_PLATES = 'group_plates'    # timed, one-time confirm
GROUP_CAR = 'group_car'          # timed, one-time confirm

#: group_id → meta (order matters for rendering)
GROUPS = [
    {
        'id': GROUP_DOCS,
        'title': 'پشت و رو گواهینامه و کارت ماشین',
        'sections': ['license_front', 'license_back', 'car_card_front', 'car_card_back'],
        'timed': False,
        'one_time_confirm': False,
        'hint': 'تصاویر گواهینامه و کارت ماشین (پشت و رو) را بارگذاری کنید؛ '
                'در پایان بخش «تأیید» بزنید (امکان تأیید دوباره وجود دارد).',
    },
    {
        'id': GROUP_PLATES,
        'title': 'شماره شاسی و پلاک‌ها',
        'sections': ['chassis_number', 'plate_front', 'plate_back'],
        'timed': True,
        'one_time_confirm': True,
        'hint': 'تصاویر را پشت سر هم بگیرید — اگر فاصلهٔ بین دو تصویر بیش از '
                '{gap} ثانیه شود، هنگام «تأیید نهایی» تصاویر این بخش حذف می‌شوند.',
    },
    {
        'id': GROUP_CAR,
        'title': 'اطراف ماشین',
        'sections': ['car_shots'],
        'timed': True,
        'one_time_confirm': True,
        'hint': 'حداقل ۴ تصویر: پشت، جلو، راست و چپ ماشین را پشت سر هم عکس بگیرید '
                '(فاصلهٔ مجاز بین دو تصویر: {gap} ثانیه).',
    },
]
GROUP_BY_ID = {g['id']: g for g in GROUPS}
SECTION_TO_GROUP = {s: g['id'] for g in GROUPS for s in g['sections']}

CAR_IMAGE_MAX_GAP_SECONDS = settings.DANA['CAR_IMAGE_MAX_GAP_SECONDS']
CAR_IMAGE_MAX_SPAN_MINUTES = settings.DANA['CAR_IMAGE_MAX_SPAN_MINUTES']
COMFORTABLE_SPAN_MINUTES = 5  # UI hint only (db + watermark keep the real limit)


def section_title(key):
    return TITLE_BY_KEY.get(key, key)
