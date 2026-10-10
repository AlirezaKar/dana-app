# سامانه ثبت پرونده و تصاویر بیمه دانا
**DANA Insurance — Case Registration & Image Capture System**

Persian RTL web application (Django + templates + custom CSS/JS) for insurance
specialists & staff. See **`spec.md`** for the full specification (original
requirements + confirmed decisions).

## Configuration — `.env` (v1.13)

Every tunable value lives in **`.env`**; the code only reads it. Start by copying
the template:

```bash
cp .env.sample .env      # every key with its default + comments
```

`.env.sample` holds the full list — Django basics (`SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS`, paths), brand links, the case rules
(`CAR_IMAGE_MAX_GAP_SECONDS`, `CAR_IMAGE_MAX_SPAN_MINUTES`), the session timeout
(`SESSION_TIMEOUT_SECONDS` / `_WARN_SECONDS` / `_MODE`), the switches
(`AUTO_SYNC_EXCEL_ON_START`, `AUTO_SYNC_ON_PAGE_VIEW`, `ACTIVITY_LOG`,
`DEV_TOOLS`) and the whole watermark block. An empty value (`KEY=`) means "use the
default in the code". A real environment variable wins over the file, and
`DANA_<KEY>` wins over `<KEY>`, so one-off runs need no edit:

```bash
DANA_CAR_IMAGE_MAX_GAP_SECONDS=3 python manage.py runserver
DANA_SESSION_TIMEOUT_SECONDS=30 python manage.py runserver
```

`.env` is the runtime file (keep your local values); `.env.sample` is the
documented template that travels with the project. The reader is
`dana/env.py` (no third-party dependency).

## Run

```bash
pip install -r requirements.txt
cp .env.sample .env            # optional — defaults are fine for a first run
python manage.py migrate
python manage.py seed_sample_data      # reads the Excel files from storage/data/
python manage.py runserver 0.0.0.0:8000   # development only
```

- App: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/` (user `admin` / `DanaDev!2026` — dev only)

`runserver` is Django's development server (auto-reload, debug pages) — it says so
itself and is not meant for a real installation. For a real one use the packaged
production server (waitress, multi-threaded, no development warning):

```bash
python manage.py serve --collectstatic        # host/port from .env (SERVER_*)
python manage.py serve --host 0.0.0.0 --port 8000 --threads 16
```

`serve` runs `DEBUG=False`, collects the static files into `statics/` and serves
them through WhiteNoise, so nothing else (nginx or similar) is required on a
single machine. Put it behind your own TLS terminator if the app must be reached
over HTTPS.

## «no such column» — repair an old database (v1.12)

If a page dies with **`no such column: app_media_caseimage.saved_name`** (or any
other missing column), the running `db.sqlite3` is older than the code: the
column was added by a later migration but this database never got it — typically
because the file was copied from another machine, or from a moment when SQLite's
journal still held the migration. `migrate` alone cannot help in that case: it
sees the migration already recorded in `django_migrations` and answers
"No migrations to apply".

```bash
python manage.py migrate          # first: apply anything still pending
python manage.py repair_db        # then: add whatever column is really missing
python manage.py repair_db --dry-run   # only report, change nothing
```

`repair_db` compares the **real** schema with the models and adds the missing
columns (`ALTER TABLE … ADD COLUMN`), so it fixes the page without touching any
data; it is safe to run twice. Images that were stored before the column existed
get an empty `saved_name` — give them their proper name with
`./watermark.sh --all --rename`.

## Excel data — put your files in `storage/data/`

The reference data is **auto-synced on every server (re)start**: files in the
**`storage/data/`** folder are re-imported (upsert, keyed on کد رایانه پرونده)
when the website starts/reloads. You can also run it manually:

```bash
python manage.py seed_sample_data          # reads storage/data/
python manage.py import_records            # same auto-discovery
python manage.py import_records --badane X.xlsx --satheth Y.xlsx   # explicit paths
```

Files are classified by file name (بدنه/badane/body vs ثالث/satheth/third).
The importer is layout-tolerant: RTL sheets, a merged title row above the
green header row, tatweel in headers (تاریـخ), thousands separators — column
position and styling don't matter, only the header words.
Header mapping lives in `app_records/importers.py`.

**Login passwords:** add a column named **رمز عبور** (or رمز / کلمه عبور / پسورد /
password) to each Excel file; its value is the login password for that
کد رایانه پرونده. The two demo files already contain `123456` for every row.
Two demo files in the real Excel layout are already in the folder — replace
them with the real files (toggle: `settings.DANA['AUTO_SYNC_EXCEL_ON_START']`).

## Startup data sync

The reference data and the login accounts are re-collected **every time the server
starts** (`runserver`, including every auto-reload) and by the one-shot commands:

```bash
python manage.py sync_data                 # Excel records + login accounts
python manage.py sync_data --excel-only    # only the Excel reference data
python manage.py sync_data --users-only    # only the login accounts
python manage.py sync_users                # only the login accounts (same as above)
```

Beside the server start, the data is **re-read automatically when an info page is opened**:
the upload page and the final page compare the Excel files' signature (name, mtime, size) and
re-import only when something changed — so saving an edited `storage/data/*.xlsx` is enough and
`python manage.py seed_sample_data` is no longer needed. Switch it off with
`DANA['AUTO_SYNC_ON_PAGE_VIEW'] = False`.

The reference Excel files do **not** carry the «رمز عبور» column any more (accounts live in the
User model), and the importer ignores any unknown columns it finds.

The sync deliberately does **not** run in `AppConfig.ready()`: at that point Django is
still initialising and any query triggers

```
RuntimeWarning: Accessing the database during app initialization is discouraged.
```

Instead `app_core/startup.py::sync_all()` is called from the custom `runserver`
command (in the serving process only), from `manage.py sync_data`, and from
`dana/wsgi.py` / `dana/asgi.py` for production servers. Everything is idempotent —
existing rows and accounts are updated, never duplicated. To switch the automatic
runs off set `DANA['AUTO_SYNC_EXCEL_ON_START']` / `['AUTO_SYNC_USERS_ON_START']`
to `False` in `dana/settings.py`.

## User activity log (فعالیت‌های کاربران)

Every meaningful action is appended to **`app_account.UserActivity`** and is visible in
`/admin/app_account/useractivity/` — **strictly read-only there** (no add / change / delete; the
detail page is a read-only form). Anonymous visits are logged too
(`username_label = "anonymous"`, `user = NULL`).

| Action | Written by |
|---|---|
| `login_success` / `login_failed` | `app_account/views.py::login` → `activity.record_login_attempt()` |
| `logout` | `app_account/views.py::logout` |
| `insurance_select`, `record_match`, `case_edit` | `app_account/views.py` (stages 2 / 3) |
| `image_upload`, `image_remove`, `car_confirm` | `app_media/views.py` |
| `finish`, `restart` | `app_main/views.py` |
| `page_view` | `app_account/middleware.py::UserActivityMiddleware` (GET only; skips static/media/admin/AJAX) |

Helpers: `app_account/activity.py` (`log_activity()`, `record_login_attempt()`, `PAGE_LABELS`,
`resolve_page_location()`), `app_account/utils.py` (`get_client_ip()`, `truncate()`),
`app_account/admin_filters.py` (`DateTimeFromToFilter`: امروز / دیروز / ۷ روز / ۳۰ روز).
Counters `login_attempt_count` + `page_view_count` live on the user profile (atomic `F() + 1`,
read-only in the admin) and the user page shows the last 20 activities of that account.
Switch the whole log off with `DANA['ACTIVITY_LOG'] = False`.

## Identification: کد رایانه پرونده & «ورود با سایر اطلاعات» (v1.10)

**The dropdowns read from the Excel data.** `storage/data/*.xlsx` is imported on server start and
re-imported whenever the signature changed on a page view (`app_core/startup.py`). The list has
three scopes, and the endpoint reports which one is in play (`/records/search/` → `scope`):

| Type | When | What is listed |
|---|---|---|
| `query` | the user typed something | **all** records of that insurance type, `istartswith`, newest first — a case from any earlier day stays reachable |
| `today` | empty query on the کد رایانه پرونده box | records whose claim was reported **today** (Jalali/Tehran) |
| `recent` | empty query, nothing reported today | the newest claims instead of an empty list + the note «امروز پرونده‌ای با تاریخ اعلام خسارت امروز ثبت نشده است…» |

That is the fix for the “the list is empty” report: the today filter used to be applied to typed
queries as well, so as soon as the Jalali date rolled over the box looked dead both on click and
while typing. `search_records_scoped()` in `app_records/models.py` now returns `(records, scope)`;
`SCOPE_NOTES` in `app_records/views.py` supplies the note, and the combobox paints it above the
list.

**One identification method at a time.** Two identifiers can point at two different cases, so:

* adding a box in the «ورود با سایر اطلاعات» popup disables the other tabs, the popup button and
  makes کد رایانه پرونده read-only;
* typing/picking a کد رایانه پرونده disables the popup button;
* removing the box (✕) or clearing the code unlocks everything again;
* the server refuses both at once (`MULTI_METHOD_ERROR` in `app_account/views.py`) — validation
  runs before anything is saved, so the message «…فقط **یک** شناسه قابل استفاده است…» appears
  without creating a case.

**Dropdown stacking.** An open list is lifted with `.cb.cb-open` (`z-index: 110`) and painted at
`z-index: 120`, so it shows **above** the sibling tabs of the popup; leaving the field closes it
(blur), so a stale list can never swallow a click.

## The tiny box in the footer — changing a rule while developing (v1.13)

At the **bottom of every page** there is one very small, unlabeled entry box. It
holds **`CAR_IMAGE_MAX_GAP_SECONDS`** — the max gap between two consecutive photos
of «اطراف ماشین و شماره شاسی ماشین» — and it changes the rule live:

- type a number → the value changes **for your session only** (stored in the
  session, never written to `.env`); the box gets an amber border while an
  override is in force, the upload page banner shows the new number and
  «تأیید نهایی» checks against it;
- empty the box → back to the `.env` value (the box fills itself with it again);
- the box only exists when `DEV_TOOLS=True` in `.env` (the default follows
  `DEBUG`), so a real installation never shows it.

Endpoint: `POST /dev/setting/` (`app_core/views.py` + `app_core/dev_settings.py`,
`EDITABLE` lists which keys may be changed — currently the two car-timing values).
The client is `DANA.initDevGap()` in `app_core/static/js/core.js`; the markup sits
in `{% block footer_extra %}` of `app_account/templates/account/login.html`.

## One identifier at a time (فقط یک شناسه) — v1.12

On the identifiers page exactly **one** search key may hold a value, because two
identifiers can point at two different cases:

- while **کد رایانه پرونده** has a value, every شناسه of «ورود با سایر اطلاعات» is
  unavailable — the popup still opens, but its fields are greyed with the reason
  ««کد رایانه پرونده» مقدار دارد؛ برای استفاده از این شناسه‌ها ابتدا مقدار آن کادر
  را پاک کنید.»;
- while an alternate identifier has a value, **کد رایانه پرونده** is disabled
  (it cannot even be clicked, so its فهرست does not open) and the other alternate
  identifiers are disabled too;
- **deleting the value frees the others at once** — the empty alternate box may
  even stay in place and be swapped for another option.

The client-side lock is `DANA.syncIdentifiers()` in `app_core/static/js/core.js`
(re-evaluated on every keystroke); the server refuses two identifiers anyway
(`MULTI_METHOD_ERROR` in `app_account/views.py`) — one identifier is accepted,
two are rejected with the amber message «فقط یک شناسه قابل استفاده است».

## GPS on the photos — removed in v1.14

There is **no GPS section any more** (owner request): the stamp holds only the
two logos + the text lines (date & time, کد رایانه, شماره پرونده, شماره پلاک,
شماره بیمه‌نامه, نام کاربری). The old `latitude` / `longitude` / `gps_accuracy`
columns were dropped from `CaseImage`.

## Watermark on every photo (واترمارک تصاویر)

Every uploaded photo gets a **transparent stamp in a bottom corner** (no background box) before
the file is written to disk — `app_media/services/watermark.py`, called from
`storage.save_temp_image()` (the bytes go to a `.part` file, are stamped, and only then do they
land at their real path). The same code runs later through a management command, so nothing has
to be re-uploaded.

What the stamp shows (lines with no value are skipped):

| Line | Source |
|---|---|
| موقعیت | GPS of the accident location, Google-Maps format `35.689200, 51.389000` + the URL `https://www.google.com/maps?q=35.689200,51.389000` |
| تاریخ و ساعت | Jalali date + time (Asia/Tehran, Persian digits) |
| کد رایانه پرونده · شماره پرونده · شماره یکتا · شماره پلاک · شماره بیمه نامه | the case/record of the submission |
| کاربر | the username that uploaded it |
| لوگوها | `img/dana-logo.png` + `img/hef.co.ir.png` (same files as the site header) |

Where the GPS comes from: the upload page asks the browser for the location when it opens
(`navigator.geolocation`, high accuracy), keeps it for the session and sends it with every
upload (`lat` / `lng` / `acc`). A denied prompt can be retried with «تلاش دوباره» or typed by
hand («ثبت دستی») — both a plain `35.6892, 51.3890` and a Google-Maps link are accepted.
No GPS at all is fine: the line is simply left out (or set `WATERMARK['FALLBACK_COORDS']`).

### Saved file names & embedded metadata (v1.11)

* **Name** — every photo is saved as **`<کد رایانه پرونده>,<تاریخ و ساعت>.jpg`**
  (Jalali, the upload time), e.g. `22208730,1405-07-02_15-23.jpg`. The Jalali date/time uses `-`
  instead of `/` and `:` because those are illegal in Windows file names. Two photos of the same
  case taken in the same minute get `-2`, `-3`, … (`…15-23-2.jpg`). The name is set **at upload**
  and kept when the case finishes (`storage/<DN-…>/<section>/`), so it survives the whole flow;
  the extension follows the real content (a phone that sends `image` with no extension still ends
  up as `.jpg`, a PNG as `.png`). The original client name is kept in `CaseImage.original_name`.
* **Comment** — the same facts the stamp shows (everything except the logos) are written into the
  image metadata as one comma-separated line:
  `موقعیت: 35.689200, 51.389000, نقشه: https://…, تاریخ و ساعت: ۱۴۰۵/۰۷/۰۲ ۱۵:۲۳, کد رایانه پرونده: …, شماره پرونده: …, شماره یکتا: …, شماره پلاک: …, شماره بیمه نامه: …, کاربر: …`
  — as `ImageDescription`, as `UserComment`, as **`XPComment` (UTF-16LE) which is what Windows
  Explorer shows under *Properties → Details → Comments***, and as the JPEG comment marker / the
  PNG `Comment` text chunk. The camera EXIF is preserved, and the orientation tag is normalised
  (once, at upload) so the stamp is never rotated twice.
* The whole thing happens in **one re-encode** at upload (`watermark.watermark_file`);
  `RENAME_FILES` / `FILENAME_SEPARATOR` / `WRITE_COMMENT` in `settings.WATERMARK` switch it off.

Existing files can be brought up to date without re-uploading:

```bash
./watermark.sh --all --rename --comment-only   # old photos: new names + the comment, no re-stamp
./watermark.sh --all --rename                  # also stamps photos that have no stamp yet
./watermark.sh --all --out /tmp/stamped        # copies that carry the new names
```

`--comment-only` never touches the pixels (JPEG is re-saved with `quality='keep'`, PNG is
lossless) and never redraws the stamp; `--rename` is idempotent, so running it twice changes
nothing.

### Manual run — `python -m app_media.services.watermark` (v1.14)

The tooling is a **single Python module** (the project runs on Windows — no
`.sh` scripts; the old `watermark.sh` / `manage.py watermark_images` are gone):

```bash
python -m app_media.services.watermark                       # photos not stamped yet (default)
python -m app_media.services.watermark --all                 # every photo of every case
python -m app_media.services.watermark --case 77777777       # one case folder
python -m app_media.services.watermark --section car_shots --force
python -m app_media.services.watermark --path storage/files/1405-07-07/77777777-palireza
python -m app_media.services.watermark --all --dry-run       # report only, change nothing
python -m app_media.services.watermark --all --out /tmp/stamped   # fresh copies, originals untouched
```

`--out` never risks a double stamp; plain `--force` re-draws the stamp **on top of** the old one,
so it is meant for files that were stored without a stamp. Photos already stamped at upload time
are marked with `CaseImage.watermarked_at`, which is what the default run uses to decide.

### Configuration & requirements

`dana/settings.py` → `WATERMARK = {ENABLED, POSITION, OPACITY, SCALE, MIN_WIDTH_FRACTION,
MAX_HEIGHT_FRACTION, LOGOS, SHOW_MAPS_URL, FALLBACK_COORDS}` (set `ENABLED: False` to store raw
uploads). The stamp never covers more than `MIN_WIDTH_FRACTION` of the width **or**
`MAX_HEIGHT_FRACTION` of the height, so it stays reasonable on small and portrait photos.

The stamping is hardened: the result is written to a temporary neighbour and only then moved into
place (a failure can never destroy the source), and if anything fails during an upload the reason
is written to the server log — run `./watermark.sh` to stamp those photos afterwards. The command
starts with a preflight that names the problem (missing TTF, Pillow without raqm, missing logo)
instead of silently doing nothing.

Persian text in the stamp needs Pillow **with raqm** and the TTF twin of the self-hosted Vazir
(`app_core/static/fonts/Vazir-{400,500,700,900}.ttf`, produced once from the woff2 files):

```bash
pip install "fonttools[woff]" brotli
python -c "from fontTools.ttLib import TTFont;\
 f=TTFont('app_core/static/fonts/Vazir-700.woff2'); f.flavor=None; f.save('app_core/static/fonts/Vazir-700.ttf')"
python -c "from PIL import features; print(features.check('raqm'))"   # must print True
```

## Session timeout (مهلت نشست ۱۰ دقیقه‌ای) — v1.12

An operator who has been inside the app for ten minutes is taken out of it
automatically:

1. **60 seconds before the end** a popup appears over the page: «مهلت نشست در حال
   پایان است» with a live countdown «۰:۴۷» and two buttons — **ادامهٔ کار** (stays
   logged in for another ten minutes) and **خروج**.
2. **If nobody reacts**, as soon as the countdown reaches zero the page shows
   «در حال خروج از سامانه…» and returns to the login page with the message
   «مهلت نشست شما به پایان رسید (۱۰ دقیقه بی‌فعالیتی). برای ادامه دوباره وارد شوید.»
3. Every visit inside the app is itself activity, so a busy operator is never
   interrupted; only ten quiet minutes end the session. The server is the judge
   (`SESSION_TIMEOUT_SECONDS`), the page only shows it.
4. Each automatic ending is written into the activity log as
   `session_timeout` — «پایان خودکار نشست پس از ۱۰ دقیقه بی‌فعالیتی» — with the
   user that was inside.

Tuning (no code change needed):

```bash
# dana/settings.py → DANA
'SESSION_TIMEOUT_SECONDS': 600,        # 10 minutes
'SESSION_TIMEOUT_WARN_SECONDS': 60,    # popup 1 minute before the end
'SESSION_TIMEOUT_MODE': 'idle',        # 'idle' = from the last request,
                                       # 'absolute' = from the login
# or from the environment (handy for a demo)
DANA_TIMEOUT_SECONDS=30 DANA_TIMEOUT_WARN_SECONDS=10 python manage.py runserver
```

Files: `app_account/middleware.py` (`SessionTimeoutMiddleware`, `close_session`),
`app_account/views.py` (`session_ping`, the `?timeout=1` notice),
`app_core/static/js/core.js` (`DANA.initTimeout`), `app_core/templates/base.html`
+ `app_core/static/css/style.css` (the popup), `app_account/models.py`
(`session_timeout` action, migration `0004`).

## One way out (دکمهٔ خروج) — v1.21

The pill in the page header is gone: the **badge next to the user's information**
(نام کاربری / نوع کاربر / مشاهدهٔ پوشه‌ها) is the only exit on the wizard pages,
and the final page keeps its own **«بازگشت به شروع»**. There are no icons anywhere
in the app any more (v1.21) — every action is a word: «حذف», «بستن», «دوربین»,
«گالری».

## Where the photos live & when the watermark is applied (v1.13)

```
storage/
├── data/                                     the Excel files (reference data)
└── files/<تاریخ>/<کد رایانه>-<نام کاربری>/     one case (open or finished)
        ├── car_card_front.jpg, plate_front.jpg …  the مقصر's photos, named by field
        └── <شماره پلاک>/                        one folder per زیان‌دیده
```

- There is **no temporary area** any more (v1.14): a photo is written straight
  into the folder of its case (`app_media/services/storage.py::save_case_image`),
  in the format it arrived in — HEIC/HEIF/DNG are stored byte-for-byte, JPEG/PNG
  are re-saved with the stamp inside.
- The watermark and the metadata comment are applied **at upload time**; if
  stamping fails for a file the raw photo is still stored and the reason is
  logged — the process never breaks (`./watermark.sh --case <…>` can stamp it
  later). HEIC/DNG cannot be stamped by Pillow and are deliberately skipped.
- `./watermark.sh` remains the manual twin: no arguments = photos that are not
  stamped yet, `--all`, `--case DN-…`, `--force`, `--out DIR` (fresh copies; names
  are kept and never overwritten), `--comment-only`, `--rename`, `--dry-run`.
- No GPS? The photos simply say **`No GPS Found`** on the stamp (and in the
  comment) instead of the coordinates — nothing blocks.

## Storage browser (مشاهدهٔ پوشهٔ ذخیره‌سازی)

The نوع بیمه page (stage 2) carries a small **«مشاهدهٔ پوشهٔ ذخیره‌سازی»** button next to the
badges; it opens the storage browser in a **new tab**.

| URL | Page |
|---|---|
| `/media/storage/` | the case folders of the logged-in user under `storage/files/<تاریخ>/…` — one link button per folder (files, size, Jalali time, thumbnails) + every file name/image, then the `storage/data` files. Read-only. |
| `/media/storage/folder/<path>/` | detail page of **one** folder: breadcrumb, its subfolders (again link buttons) and its files (name, label, size, pixel size, Jalali time, preview, نمایش/دانلود) |
| `/media/storage/raw/<path>` | one file, inline (used for the thumbnails) |

Implementation: `app_media/storage_views.py` + `app_media/templates/media/storage_{index,folder}.html`
+ the `.storage-page` block in `app_core/static/css/style.css`. It is **read-only** (never
writes/moves/deletes), clamps every path to `STORAGE_ROOT` (404 otherwise) and requires the
wizard session or a staff account. Section folders are labeled with `app_media.constants.TITLE_BY_KEY`.

## Brand links

`dana/settings.py` → `BRAND_URLS = {'DANA_URL': …, 'HEF_URL': 'http://127.0.0.1:6060'}`.
Both are exposed to every template as `{{ DANA_URL }}` / `{{ HEF_URL }}` (logos + footer), so a
link change is a one-line edit in the settings instead of four template files.

## Flow

1. **Step 1 — login & registration (login is separate from the insurance process):**
   - **Page 1 — ورود به سامانه:** pick the **نوع کاربری** (کارشناس / نماینده / بیمه شده /
     خدمات غیرحضوری); the **login box opens below the cards** and asks for **نام کاربری** +
     **رمز عبور**.
     Authentication uses the **User model only** (`auth.User` + `UserProfile.user_type`) — no
     insurance table and **no کد رایانه پرونده** is read. The username is a **free name** that
     only has to **start with the type's prefix letter**:
     **کارشناس → `palireza`**، **نماینده → `nhajir`**; بیمه شده / خدمات غیرحضوری have no prefix.
     The prefix is not drawn as a badge next to the field — you type it yourself and the rule is
     checked on login (a hint under the field shows an example).
     The **password is optional**: an account with a password needs it (normal Django password
     field), an account without one **signs in with the username alone** — the page detects that
     live (`/login/check-user/`) and hides the password field.
   - The insurance process then starts on its own pages: **Page 2 — نوع بیمه** (بدنه = green
     theme / ثالث مالی = pink) and **Page 3 — شناسه‌های پرونده** (کد رایانه پرونده empty;
     «ورود با سایر اطلاعات»). The case's نوع کاربری comes from the logged-in account, and a
     **«خروج»** link in the badge row ends the session at any time.
   - **Managing accounts:**
     ```bash
     python manage.py seed_users                     # demo set (one per user type)
     python manage.py create_user palireza 123456 --user-type specialist --name "علی رضایی"
     python manage.py create_user nreza --user-type agent        # account WITHOUT a password
     python manage.py create_user nreza --set-password 123456    # enable the password later
     python manage.py create_user nreza --no-password            # disable it again
     ```
     Demo accounts created by `seed_users`: `palireza` / `nhajir` / `alireza` = password
     `123456`, and `remote1` = **no password** (signs in with the username only). Accounts can
     also be managed in `/admin/` — the kind of کاربر سامانه sits in the User page's inline, so
     the user and its نوع کاربری are created in **one step** (the prefix rule is validated by the
     inline formset, which reads the username from the parent form).
2. **Step 2 — uploads:**
   - کارت ماشین (روی/پشت) and گواهینامه (روی/پشت): **exactly one image each**,
     uploaded immediately.
   - **اطراف ماشین و شماره شاسی ماشین**: one section, **unlimited images** (min 5),
     with a single **«تأیید نهایی»** button. Upload times are tracked; on pressing the button
     the server checks that every consecutive gap is ≤ **10 s** (and the whole span ≤ 10 min).
     A violation → popup «زمان زیادی طول کشید!» and the section's images are discarded.
     The button can be pressed **only once** (warned in the UI before and after).
3. **Step 3 — done:** the reference page layout with the unique number
   `DN-<JJJJ-MM-DD>-<6 chars>`, the AI-review note, **all information** (registration data,
   entered values, the full reference record) and the uploaded images grouped with labels
   and capture times, plus «بازگشت به شروع».
   The upload page shows the same full information panel (with «ویرایش اطلاعات»), the slot
   titles carry no counters, and the finish button is centered below everything.

Images are written straight into
`storage/files/<تاریخ>/<کد رایانه>-<نام کاربری>/…` — a زیان‌دیده gets its own
subfolder named after its plate (watermark hook:
`app_media/services/watermark.py`).

## Layout

| Path | Role |
|---|---|
| `dana/` | Django project (settings, urls, wsgi/asgi) |
| `app_core/` | base template, jalali tags, digits utils, Vazir fonts (self-hosted woff2), CSS/JS |
| `app_account/` | login flow (user type / insurance type / record matching) |
| `app_records/` | `BodyInsurance`, `ThirdPartyInsurance` + Excel import + search API |
| `app_main/` | wizard steps, `CaseSubmission`, finish orchestration, unique number |
| `app_media/` | `CaseImage`, upload/remove/serve, timing validation, storage service |
| `storage/data/` | your Excel files — auto-imported on every server start |
| `storage/` | case images (runtime: tmp/ while working, `<unique_number>/` after finish) |
| `staticfiles/` | output of `python manage.py collectstatic` |
| `plan/` | reference material (screenshots, reference templates, logos, plate, Excel previews) |

Branding: `dana-logo.png` links to https://www.dana-insurance.com/, `hef.co.ir.png`
links to http://hef.co.ir; footer: «تمامی حقوق محفوظ است.» / «بیمه دانا - هوشمند ارتباط فرادید».

## Round 20 — v1.14 (the «کد شعبه» / victims / bulk-upload release)

**Watermark.** Single module `app_media/services/watermark.py` (CLI `python -m
app_media.services.watermark`, see above). **No GPS section any more** — the
stamp is: the two logos + «تاریخ و ساعت، کد رایانه پرونده، شماره پرونده، شماره
پلاک، شماره بیمه‌نامه، نام کاربری».

**Login.** «بیمه شده» and «خدمات غیرحضوری» are gone (only «کارشناس» and
«نماینده»). The form is shown **immediately** — no user-type cards. The type
comes from the username's first letter: `p` → کارشناس, «د» (or legacy `n`/`d`)
→ نماینده; any other first letter is **the only** validation error. Password
is optional per account (the page asks the server with
`/login/check-user/?username=` and hides the password box for password-less
accounts).

**Upload page.** The old «اطلاعات» page is gone: its کد رایانه selector +
the small scrollable «show all infos» record panel now sit at the top of the
upload page («یافتن پرونده»). Only **one** identifier at a time (the
«ورود با سایر اطلاعات» popup keeps the alternates + «کد مربوط به پلاک جدید»
branch). The three entry fields of «بیمه شخص ثالث» (شماره پلاک/نام/کدملی) are
removed — a victim with those fields is added explicitly instead.

**Upload groups** (the same three for «مقصر» and for every «زیان‌دیده»):

1. **پشت و رو گواهینامه مقصر + پشت و رو کارت ماشین** — bulk (multi-image),
   **no timer**, one confirmation button at the end which can be pressed
   **again and again** («تأیید این بخش»);
2. **شماره شاسی + پلاک جلو + پلاک پشت** — bulk, **one shared timer**
   (same seconds in every part), one-time «تأیید نهایی»;
3. **اطراف ماشین** (min 4) — bulk, shared timer, one-time; **شماره شاسی is no
   longer** part of it.

A timed group's confirm runs the gap/span check server-side; on a violation the
group's photos are discarded and the section resets («تصاویر این بخش حذف
شدند…»).

**Victims.** «اضافه کردن زیان دیده» (available again under every added victim)
opens 4 boxes — نام، نام خانوادگی، کد ملی، شماره ماشین/پلاک (**پلاک الزامی**,
the rest optional) — and the same three upload sections. Victim photos go to
`storage/files/{date}/{کد رایانه}-{username}/{شماره پلاک}/`; every image is
named after its field (`car_card_front.jpg`, `chassis_number-2.jpg`, …).

**Folders.** Every case folder is created at «یافتن پرونده» as
`storage/files/{Jalali date}/{کد رایانه}-{username}`. Every ثبت پرونده is
assigned to the user who completed it (`CaseSubmission.completed_by` /
`completed_username`), and the folders page shows **only folders that end with
the logged-in username** (plus the DB ownership check).

**کد شعبه.** Both insurance models carry a `branch_code` («کد شعبه»). Every
کاربر سامانه gets one or more **شعبه‌ها** (`UserProfile.branches`); record
lookups (کد رایانه، کد ملی، …) only return rows of the user's branches
(a user with no branches sees everything).

**UI.** The timeout warning has **no icon** and only appears in the **last 15
seconds**. The custom plate component has no white pixels on its right edge.
The native browser back button behaves like the app's back button
(`window.DANA_BACK` + `history.replaceState` guard).

**Login page** also shows the storage browser badge («پوشه‌های من»).

## Round 21 — v1.14.1 (one entry, one page, one plain watermark)

- **The second page is gone.** After login you go straight to the upload page.
  The old «انتخاب نوع بیمه» / «اطلاعات» page is removed: the **insurance type
  is detected from the found record** (the code is looked up in both the بدنه
  and the شخص ثالث tables — when it exists in both, a pick list appears). The
  only thing the user enters is **«کد رایانه پرونده»**.
- **Only one identifier.** «ورود با سایر اطلاعات» (کد ملی/شماره ماشین/بیمه
  نامه/پلاک) is removed from the finder — the upload page keeps just the کد
  رایانه box + the small scrollable record panel (+ the «پلاک تغییر کرده»
  branch for بدنه).
- **Footer fixed.** The long template comment in the footer used to render as
  visible text (Django comments cannot span lines) — it is deleted; the footer
  keeps only the tiny timer number input (`CAR_IMAGE_MAX_GAP_SECONDS`).
- **Watermark — the second, simple one.** `watermark.py` now has
  `simple_watermark_file()` / `run_simple_for_submission()`: **only «کد
  رایانه پرونده» as plain text** (no logos, no styling). The program is
  **activated when the upload is finalized** («اتمام و ساخت پوشه») and stamps
  every photo of the case (مقصر + زیان‌دیده‌ها). Photos are stored raw until
  then. Manual run: `python -m app_media.services.watermark --simple`.

## Round 22 — v1.15 (the نوع بیمه page is back, plate widget, no duplicate files)

- **Flow fixed (the «second page» misread).** The **«انتخاب نوع بیمه» page is
  back** after login (person ثالث / بدنه) — after choosing the type you go
  **directly to the upload page**. What must *not* exist is the standalone
  «یافتن پرونده» screen: the **کد رایانه entry lives inside the upload page**
  and the insurance details table shows right there after entering the code;
  the upload sections open on the same page. The chosen type scopes the record
  lookup first (the other table is only a fallback, so a code never dead-ends).
  Back from the upload page returns to the نوع بیمه page.
- **One «اضافه کردن زیان دیده» button.** The per-victim extra trigger is gone;
  only the bottom button remains, and it hides while the victim form is open.
- **Plate template for the victim.** The victim's «شماره پلاک» now uses the
  same Iranian plate widget (۲ رقم · حرف · ۳ رقم · سریال «ایران» اختیاری) as
  the «پلاک تغییر کرده» branch — composed as `94س225` / `94س225-21`.
- **No success popups** — except the timed sections. Confirming «گواهینامه و
  کارت ماشین» shows a small message (toast) only; the two timed groups keep
  the popup. The popup after «اتمام و ساخت پوشه» («فایل در چندین مکان امن…»)
  is removed as well.
- **No duplicate files.** After finalizing + watermarking only the watermarked
  files remain on disk: a single-photo field is **replaced** on re-upload (no
  `car_card_front-2.jpg`), the staged `*.upload` file is **moved** into place
  (never copied), stamping writes through an atomic neighbour with retries
  (no `*.wm-tmp` can linger), and finalize sweeps any stray staging file.
  Only «عکس‌های اطراف ماشین» keeps multiple photos per field.


## Round 23 — v1.16 (one `statics/` + one `templates/` folder; the image viewer works)

- **One `statics/` folder for every static file.** Layout is
  `statics/{css, js, font, img}` — the sources the project ships — and
  `python manage.py collectstatic` merges the rest (Django admin's files)
  into `statics/admin/` (the same folder; STATIC_ROOT = `statics`). The old
  tracked `staticfiles/` snapshot is deleted and git-ignored — it had gone
  stale and could serve outdated css/js. `STATIC_URL` is `/static/`.
- **One `templates/` folder.** All eight templates live under
  `templates/` with namespaced names (`base.html`, `account/login.html`,
  `main/upload.html`, `main/done.html`, `main/_party_groups.html`,
  `main/_victim_block.html`, `media/storage_index.html`,
  `media/storage_folder.html`); `TEMPLATES['DIRS']` points there. Every
  `extends`/`include`/`{% static %}` relation is unchanged — the app folders
  no longer carry duplicate template/static trees.
- **Cache-busting that actually busts.** The `?v=1.14.0` string was
  hardcoded in three templates and never bumped, so browsers held on to old
  js/css for weeks (the reason earlier fixes looked like they "did not
  change"). Now every asset link uses `?v={{ STATIC_VERSION }}` with a
  **single knob** — `STATIC_VERSION` in `dana/settings.py` (env
  `STATIC_VERSION`) — currently `1.16`. Bump it whenever static assets
  change.
- **The image viewer on the evaluation page is fixed and hardened.**
  Clicking a photo opens the full image in the lightbox again: each gallery
  item gets its own click handler (plus the document-level delegate for
  dynamically added thumbnails), the overlay carries a legacy
  `top/right/bottom/left` fallback, a missing file shows «نمایش تصویر ممکن
  نشد» instead of a blank overlay, and `media_serve` always answers with a
  real `image/*` content type (never `application/octet-stream`, which made
  some browsers download the file instead of displaying it).
- **`P0.html` and `pf.txt` are deleted** (answered here as requested): `P0.html`
  was a saved browser snapshot of the old «مرحله ۱ — اطلاعات» page from before
  v1.6 (a reverse-engineering leftover), and `pf.txt` was a curl cookie jar
  with expired session tokens. Nothing referenced either file; both are gone.
- The watermark program's font/logo paths now resolve through settings
  (`STATIC_SOURCES` + the `font` prefix of `STATICFILES_DIRS`) instead of a
  hardcoded app folder — nothing to fix if the static layout moves again.


## Round 24 — v1.17 (upload-page layout, honest timing-cancel, watermark fixed)

- **Popups on uploads only for the timing-cancel.** «تأیید نهایی» of a timed
  section no longer pops a success dialog — every group confirms with a small
  toast. The only popup left is the cancel error itself («زمان زیادی طول
  کشید!») shown when the timing rule discards a section's photos.
- **The timing-cancel keeps your work and your place.** When the timing rule
  fires, **only that section's photos** are removed («گواهینامه و کارت ماشین»
  and the other groups keep every image) and the page **stays exactly where it
  is** — the cancelled thumbnails disappear in place, nothing navigates away,
  no page reload, and you never go back to the نوع بیمه step. The upload page
  also renders server-side messages (e.g. finish-time timing errors) that used
  to be invisible.
- **Separator added** between the case-information section and the image
  sections (a labeled divider — «📷 بارگذاری تصاویر»).
- **Single-photo fields are now a compact grid.** The seven one-photo fields
  (گواهینامه/کارت ماشین ×۲, کارت ماشین, شاسی, پلاک‌ها) sit in one or two grid
  rows with small «دوربین» / «گالری» buttons instead of a long vertical list.
  The bulk field «اطراف ماشین» keeps the wide multi-photo layout unchanged.
- **The watermark is back on every image.** Finalize stamps the plain «کد
  رایانه» text (nothing else) into **every** photo, and the served images are
  now `Cache-Control: no-store` — before, browsers kept showing the cached
  unstamped photo under the same URL (that is why the stamp «did not appear»).
  Stamping verifies the text actually rendered and falls back to Pillow's
  bundled font if a TTF is broken; any real failure is written to the activity
  log instead of being swallowed. After finalize only the stamped files remain
  (stamped in place — no copies, scratch files swept).
- **The زیان‌دیده plate widget is centered** in its row.
- A finished case is **re-attached** instead of orphaned: if the session dies
  mid-flow and you log in and enter the same کد رایانه again, the unfinished
  case (with all its photos) is picked up where you left it.

## Round 25 — v1.18 (static texts, the full watermark, optional QR)

- **The three group texts are yours to edit.** The titles and banners of the
  three upload groups — «پشت و رو گواهینامه و کارت ماشین», «تصاویر را پشت سر هم
  بگیرید» and «حداقل ۴ تصویر: پشت، جلو، راست و چپ ماشین…» — are written as
  plain static HTML inside `templates/main/_party_groups.html`, so they can be
  edited in the template file without touching Python (only the numbers stay
  live). All your previous text edits are kept as they are.
- **The watermark now carries the full stamp.** Finalize stamps four lines and
  the two logos on every photo: «کد رایانه», «شماره پرونده», «نام کاربری» and
  «تاریخ و ساعت» (Jalali, Persian digits) — beside `dana-logo.png` and
  `hef.co.ir.png`. The pipeline is exactly the same as before: in-place at
  finalization, only the stamped files remain, images serve with `no-store`.
- **Optional QR code (never breaks anything).** When the optional `qrcode[pil]`
  package is installed, a QR code is stamped to the left of the texts encoding
  a link to the new public page `/wm-info/` (کد رایانه، شماره پرونده، نام
  کاربری، تاریخ و ساعت + the two logos). Scanning it opens that page. If the
  package is missing or the QR fails for any reason, **the text watermark is
  stamped anyway** — the QR is a bonus, never a dependency.
- The QR link uses the request's own address (works on any host); for
  command-line runs set `PUBLIC_BASE_URL` in `.env` — without any base URL the
  QR is simply skipped.

## Round 26 — v1.19 (smaller on small photos, sharper everywhere, no garbled labels)

- **The stamp scales with the photo.** Small images used to get the same big
  watermark — now the whole block (texts + logos + QR) shrinks with the image
  and is never taller than 38% of it (a 230×110 thumbnail gets a ~35 px corner
  mark instead of a half-image banner; a 4000×3000 photo keeps it to ~16%).
- **The photo stays sharp.** Re-saving after the watermark now uses JPEG
  quality 95 with 4:4:4 (no chroma subsampling) — measured ~48 dB vs the old
  ~35 dB, i.e. the re-encode is visually lossless instead of softening small
  photos. The text is drawn at 2× and downscaled, so the strokes stay crisp at
  every size.
- **The Persian labels are gone — the values read cleanly.** The labels
  («کد رایانه:», «شماره پرونده:» …) printed garbled because the Pillow wheels
  cannot shape Persian letters; the stamp now shows just the four values (کد
  رایانه، شماره پرونده، نام کاربری، تاریخ و ساعت in that order) which are
  Latin digits / Persian digits and always readable. This also makes the stamp
  much more compact.
- **The QR only appears when it can be scanned.** On tiny photos the QR would
  be a useless smudge (and eat the little space there is) — it is now skipped
  below ~88 px and its URL uses ASCII digits so the code stays light.
  Fail-safe behaviour is unchanged: QR problems never touch the text stamp.
- **No QR on your photos? Install the optional package.** The QR needs the
  `qrcode` package — run `pip install "qrcode[pil]"` (or
  `pip install -r requirements.txt`) in the same environment the app runs in.
  Without it the app stamps the text watermark only, and now writes a clear
  warning to the console/log instead of skipping silently.

## Round 27 — v1.20 (custom text + on/off toggles in `.env`)

- **Custom watermark text.** Put any text in `.env` as
  `WATERMARK_CUSTOM_TEXT=` and it is stamped as an extra line under the four
  values — your company/branch name, a note, whatever you like. Persian and
  Latin both work.
- **On/off toggles in `.env`.** `WATERMARK_CUSTOM_TEXT_ENABLED=false` hides
  the custom text and `WATERMARK_QR_ENABLED=false` never stamps the QR code —
  without touching the code, and without affecting the rest of the watermark.
- **Persian text is now properly joined.** The garbled-label problem was
  missing letter shaping in Pillow; the stamp now shapes Persian/Arabic text
  through the pure-Python `arabic-reshaper` + `python-bidi` pair (installed
  via `requirements.txt`). If those packages are missing the stamp still
  renders — just unshaped — and never breaks.

## Round 28 — v1.22 (consistent watermark + scannable QR page + no code on the frontend)

- **The watermark is now consistent.** The stamp is built as separate transparent
  layers (QR, logos, text) that are composited **once**, and every size is a
  *share of the photo* (each logo 15 % of the width, the QR 10 %, the text 3.2 %
  of the height, 2 % margin) — a 600 px thumbnail and a 12 MP photo get the exact
  same stamp. The old absolute pixel caps (font 5–64 px) and the hand-picked
  coordinates are gone; those were why the result looked different at different
  resolutions. The input is normalised first (`exif_transpose` + RGBA) so phone
  photos are never stamped sideways, and the file is saved in its **original
  format** with DPI + ICC preserved.
- **Config consistency.** `simple_overlay()` used to fall back to the defaults
  while the app passed `settings.WATERMARK`, so with `WATERMARK_POSITION` set in
  `.env` the two stamped different corners. Everything resolves through one
  `_cfg()` now.
- **A QR you can actually scan.** `ERROR_CORRECT_H`, a real 4-module quiet zone,
  integer-pixel module scaling (no blurry squares) and a semi-opaque white plate
  behind the code while the modules stay fully opaque. Verified with a real
  decoder: it reads off the stamped photo; when a code could not possibly scan
  (tiny photo) it is skipped and logged instead of being smeared on.
- **The QR opens a page with everything.** The code links to the public
  `/wm-info/` page built from the app's own address (`PUBLIC_BASE_URL` in `.env`,
  or the address the request arrived on — so it is correct behind a proxy too).
  The page shows **کد رایانه، شماره پرونده، نام کاربری، تاریخ و ساعت، شماره پلاک و
  شماره بیمه نامه** (a زیان‌دیده's photos carry that party's own plate). Old
  pre-v1.22 QR links with the long parameter names still open correctly.
- **No codebase on the frontend.** A multi-line `{# #}` note in
  `core/_brand_logos.html` was leaking maintainer text (settings names, paths)
  into every page's View Source — it is a `{% comment %}` now, and the whole
  template tree was audited for the same leak. The storage browser no longer
  prints the absolute server path. With `DEBUG=False` you get a branded Persian
  404/500 (no traceback); with `DEBUG=True` the Django yellow screen appears, as
  requested. Cookies get `SameSite=Lax` in production and `ENFORCE_HTTPS=True`
  (off by default) adds HSTS + secure cookies behind a real TLS terminator.
- **Static caching.** In production `/static/` is served with a one-hour
  `Cache-Control`, and the logos carry the same `?v=STATIC_VERSION` cache-buster
  as the css/js.
