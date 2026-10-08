# بیمه دانا — سامانه ثبت پرونده و تصاویر
## `spec.md` — Requirements & Technical Specification

> Status: **v1.5 — IMPLEMENTED.** The full application is built and tested end-to-end
> (user type + independent digits-only login on page 1, 3 wizard pages, search "today" filter,
> uploads,
> 10 s / 10 min car-group timing validation, finish → `storage/<unique_number>/…`, upload page
> with the full info panel, done page, restart).
> See `README.md` for run instructions. C3/C5/C6 were confirmed by the owner
> (no auto-fill; شاسی ≥1 and in the timing group; 10 seconds confirmed).
> Remaining items marked **⚠️** in section 10 are informational (A1/A3/A4/A5 conventions).
>
> **v1.2 owner changes (2026-09-22):** login is now **3 pages** (user type → insurance type →
> identifier boxes; theme applies from page 2); page buttons are **text-only** (no icons);
> checkbox label is now **«پلاک خودرو عوض شده است»**; font is **Vazir** (self-hosted woff2,
> farsi-digits variant); `seed_sample_data` / `import_records` read Excel files from
> **`storage/data/`** (auto-classified by file name; demo xlsx files included).
>
> **v1.3 owner changes:** third-party **شماره پلاک box is now a searchable dropdown**; footer is
> **«تمامی حقوق محفوظ است.»** + centered **«بیمه دانا - هوشمند ارتباط فرادید»** (both linked);
> **hef.co.ir logo** next to the dana logo; **pytz** in requirements; **STATIC_ROOT** set;
> **Excel auto-sync on every server (re)start**; layout-tolerant importer (RTL sheet, title row,
> tatweel); file-code prefix badge.
>
> **v1.4 owner changes (2026-09-23):**
> 1. **Authentication** — page 1 = کاربری + frame with «کد رایانه پرونده» and «رمز عبور».
>    نام کاربری = role letter (p/n) + code; password comes from the new Excel column
>    **رمز عبور** (`login_password`). Going back to page 1 clears the session and requires re-login.
> 2. **Record info panel** — selecting a file code / policy number shows **all fields** of that
>    record in a panel below the box (`/records/details/`).
> 3. **Alt identifiers popup** — replaced the «نمی‌دانم» checkbox cascade with a button that opens
>    expandable options (کد ملی / شماره ماشین / شماره بیمه نامه / شماره پلاک); one choice at a
>    time, each adds a value box used to find the case.
> 4. **Dropdowns** — boxes show available values with an **empty query** (no typing needed);
>    typing filters by prefix (`istartswith`).
> 5. **Plate component fixed** — stores exactly like the Excel samples: plate `94س225` +
>    separate 2-digit serial.
> 6. **Upload sections reworked** — کارت ماشین and گواهینامه: **1 image each**; «اطراف ماشین و
>    شماره شاسی ماشین»: single section, unlimited, with a **single «تأیید نهایی» button**;
>    gaps ≤ 10 s checked at confirm (violation → popup + discard); the button is usable once and
>    the section locks afterwards.
> 7. **Done page** — reference step-3 layout + all collected information (registration, entered
>    values, full reference record) and the images grouped with labels and capture times.
>
> **v1.5 owner changes (2026-09-23):**
> 1. **Login is completely separate from the insurance process; it lives in the User model.**
>    Page 1 shows the four نوع کاربری cards and, as soon as one is picked, the **login box opens
>    below them** (original frame look) asking for **نام کاربری** + **رمز عبور**. Authentication
>    reads **only the User model** — Django's auth user + `app_account.UserProfile.user_type`;
>    no insurance/bimeh table and **no کد رایانه پرونده** is involved:
>    * the username is a **free name** (letters, digits, `.`, `-`, `_`) that must **start with the
>      prefix letter of the type**: **کارشناس → `p…`** (e.g. `palireza`), **نماینده → `n…`**
>      (e.g. `nhajir`); بیمه شده / خدمات غیرحضوری have no prefix (any username). The prefix is
>      **not shown as a badge next to the field** — the user types it (only a hint/example is
>      displayed) and the rule is enforced when logging in.
>    * the **password is optional per account**: an account with a usable password needs it
>      (Django hashers), an account **without** a usable password signs in with the username
>      alone — the login page hides the password field for those accounts (checked live through
>      `/login/check-user/`).
>    * the selected نوع کاربری must match the account's stored type, otherwise
>      «این حساب از نوع «…» است؛ …».
>    * accounts are managed with `manage.py create_user` / `seed_users` or the admin
>      (Django's User page with the کاربر سامانه inline, so user + نوع کاربری are created in
>      **one step**; the prefix rule of the inline is checked by
>      `app_account.admin.UserProfileInlineFormSet` because the inline is validated before the
>      new parent user exists — `UserProfile.clean()` only validates when a parent is attached);
>      accounts are **not** derived from the records any more.
>    * «بازگشت»/`?stage=2|3` always wins over the `case`-exists redirect, so editing a saved
>      case and stepping back to نوع بیمه returns to that page instead of the upload page.
>    After a successful login the insurance process starts on its own page (نوع بیمه) and the
>    case's نوع کاربری comes from the account. A «خروج» link ends the session at any time.
> 2. **Badges are informational** — username / نوع کاربری / نوع بیمه only; no change buttons
>    (navigation is via the back links `?stage=2` and the «خروج» link).
> 3. **کد رایانه پرونده starts empty** — no auto-fill; clicking the box lists the values
>    (today's cases), typing filters by the starting digits; manual typing is allowed.
> 4. **«ورود با سایر اطلاعات»** — the alt-identifier popup: one-click expandable options, no
>    magnifier icons; options (کد ملی / شماره ماشین / شماره بیمه نامه / شماره پلاک) are read
>    from the DB model of the selected insurance type and are searchable the same way
>    (empty query = list, typed = starts-with), in the correct (body/third) model.
> 5. **Upload page** — the info box now shows **all** information exactly like the final page
>    (record fields + entered values) next to «ویرایش اطلاعات»; **all image-count labels
>    removed** («یک تصویر», `1/1`, `1/0`, «حداقل ۵ تصویر», `5/0`).
> 6. **Finish** — button centered, no text inside the frame, and the final page is reached
>    reliably: the JS used to disable the button inside its own click handler, which made
>    Chrome cancel the form submission (folder created, page never shown). Fixed by
>    disabling on `submit` via `setTimeout(…, 0)`.
>
> **v1.6 owner changes (2026-09-23):**
> 1. **User activity log** — `app_account.UserActivity` records every meaningful action
>    (login success/failure, logout, page views, insurance selection, record match/case edit,
>    image upload/remove, final car confirm, finish, restart) with user, username label,
>    user type, Persian description, subject, path, url name, page label, method, IP and
>    User-Agent. Written **by the view/middleware that owns the event** — never from the admin —
>    and **strictly read-only in the admin**: no add, no change, no delete
>    (`has_add_permission` / `has_change_permission` / `has_delete_permission` all `False`;
>    add/change/delete POSTs return 403, the detail page is a read-only form).
>    Anonymous visits are logged with `username_label='anonymous'` and `user=None`.
> 2. **Page-visit middleware** — `app_account.middleware.UserActivityMiddleware` appends one
>    `page_view` row per meaningful GET; non-GET, `/static/`, `/media/`, `/admin/`, favicon,
>    AJAX endpoints (`records_search`, `records_details`, `check_user`, media/… ) and any
>    response ≥ 400 are skipped. Persian labels come from `PAGE_LABELS`; new routes should be
>    added there.
> 3. **Atomic counters** — `UserProfile.login_attempt_count` / `page_view_count` are bumped with
>    `F(...) + 1` (no read-modify-write) and are read-only in the admin.
> 4. **Brand links** — `settings.BRAND_URLS` (`DANA_URL`, `HEF_URL`) exposed to templates as
>    `{{ DANA_URL }}` / `{{ HEF_URL }}`.
> 5. **Page-view Excel re-sync** — the info pages re-import `storage/data/*.xlsx` only when the
>    file signature changed (`storage/.excel_signature.json`); `seed_sample_data` is no longer
>    needed. The Excel files no longer contain the «رمز عبور» column.
>
> **v1.7 owner changes (2026-09-23) — storage browser:**
> 1. **Small button on the نوع بیمه page** — «مشاهدهٔ پوشهٔ ذخیره‌سازی» sits next to the
>    informational badges (stage 2 only) and opens `/media/storage/` in a **new tab**
>    (`target="_blank"`).
> 2. **Storage browser** — `app_media/storage_views.py` + `app_media/templates/media/`:
>    the index lists **all content of `storage/tmp`** in a labeled, organized way — one link
>    button per session folder (file count, size, Jalali last change, thumbnail previews) plus a
>    flat list of every file (names + images) — and, below that, the Excel data files
>    (`storage/data`) and the final case folders (`storage/DN-…`). **Every folder button opens
>    its own detail page** `/media/storage/folder/<path>/` with breadcrumb, subfolder buttons and
>    file cards (name, label, size, pixel size, Jalali time, preview, نمایش/دانلود). Files are
>    served inline by `/media/storage/raw/<path>`.
> 3. **Read-only & clamped** — the browser never creates, moves or deletes anything; a requested
>    path that escapes `STORAGE_ROOT` (`..`) or does not exist is a 404; the pages need the
>    wizard session (or a staff account) and otherwise redirect to the login page.
> 4. **Activity log** — the browser pages are logged as `page_view` with Persian labels
>    («مشاهدهٔ پوشهٔ ذخیره‌سازی» / «جزئیات پوشهٔ ذخیره‌سازی»); `storage_raw` was added to
>    `NON_PAGE_ROUTES` so serving a file is not logged as a page view.

> **v1.8 owner changes (2026-09-23) — image watermark:**
> 1. **Automatic stamp on every upload** — `app_media/services/watermark.py` (+ the call in
>    `storage.save_temp_image`) burns a transparent overlay into the photo *before it is saved to
>    its file on disk* (staged as `.part` → stamped → renamed). Fields: the two brand logos,
>    GPS in Google-Maps format, Jalali date + time, کد رایانه پرونده, شماره پرونده, شماره یکتا,
>    شماره پلاک, شماره بیمه نامه, نام کاربری. Corner, opacity, size, logos and maps-URL are
>    settings (`settings.WATERMARK`).
> 2. **GPS capture** — the upload page asks `navigator.geolocation` (high accuracy) once, keeps
>    the fix for the session (`sessionStorage`), shows it in a status bar («موقعیت ثبت شد …»)
>    with «تلاش دوباره» and «ثبت دستی» (accepts `35.6892, 51.3890` and Google-Maps links), and
>    sends `lat`/`lng`/`acc` with every upload. Stored per image
>    (`CaseImage.latitude/longitude/gps_accuracy`, migration `app_media/0003`).
> 3. **Manual twin** — `manage.py watermark_images` (`--all`, `--case`, `--section`, `--path`,
>    `--force`, `--out`, `--dry-run`, `--limit`) re-stamps files already on disk; default scope is
>    the photos not stamped yet (`CaseImage.watermarked_at` = NULL).
> 4. **Persian type in the stamp** — Pillow **with raqm** + the TTF twins of the self-hosted
>    Vazir font (`app_core/static/fonts/Vazir-*.ttf`, converted once from the woff2 files with
>    fontTools); the stamp is white text with a soft dark halo, 85 % opacity, ≈2.6 % of the short
>    side, never wider than 55 % of the image.

> **v1.10 owner fixes (2026-09-24) — identifier lists, one-method rule, dropdown layering, watermark:**
> 1. **کد رایانه پرونده reads the Excel data again** — `search_records_scoped()` returns
>    ``(records, scope)``: a typed query searches **all** records of that insurance type (any
>    date), an empty query on the code box shows today's claims, and when nothing was reported
>    today it falls back to the newest claims with the note shown above the list. The old code
>    applied the today filter to typed queries too, so after the Jalali rollover the box listed
>    nothing on click *and* while typing.
> 2. **One identification method only** — adding an «ورود با سایر اطلاعات» box disables the other
>    tabs, disables the popup button and makes کد رایانه پرونده read-only; entering a code
>    disables the popup button; removing the box or clearing the code unlocks everything. The
>    server refuses two identifiers at once (`MULTI_METHOD_ERROR`, checked **before** anything is
>    saved).
> 3. **Dropdown layering** — the open list is lifted with `.cb.cb-open` (z-index 110/120) so it
>    paints above the sibling tabs of the popup (`.alt-option { overflow: visible }`), and blur
>    closes it so a stale list cannot swallow clicks.
> 4. **Watermark hardening** — atomic write (temp neighbour + `os.replace`), the failure reason is
>    logged instead of swallowed, `MAX_HEIGHT_FRACTION` keeps the stamp reasonable on small and
>    portrait photos, `preflight()` names environment problems, and `./watermark.sh` wraps the
>    management command so it also works in a freshly reset sandbox (installs requirements,
>    rebuilds the Vazir TTF twins).

> **v1.11 owner changes (2026-09-24) — file naming + embedded metadata:**
> 1. **File name** = **کد رایانه پرونده + «تاریخ و ساعت»** separated by a comma
>    (`22208730,1405-07-02_15-23.jpg`); `-` instead of `/`/`:` for Windows safety, `-2`/`-3`
>    for photos of the same minute. Set at upload, kept at finish; the extension follows the
>    real content; `CaseImage.saved_name` stores it (migration `app_media/0004`).
> 2. **Metadata comment** — every line of the stamp except the logos is also written into the
>    image: `ImageDescription`, `UserComment`, ``XPComment`` (UTF-16LE → Windows *Properties →
>    Details → Comments*) and the JPEG COM / PNG `Comment` chunk, as one comma-separated line.
>    The camera EXIF is preserved and the orientation tag is normalised at upload.
> 3. **Manual tooling** — `./watermark.sh` wrapper; the command gained `--comment-only`
>    (metadata without redrawing the stamp, pixels untouched: JPEG `quality='keep'`) and
>    `--rename` (bring old files to the new name, idempotent), plus a preflight and honest
>    empty-state messages.

> Conventions: backend identifiers (variables, fields, app names) are **English**; everything
> user-facing (labels, `verbose_name`, placeholders, messages) is **Persian** with Persian digits.

---

## 1. Purpose & Scope

A Persian **RTL** web application for **Dana Insurance** (بیمه دانا) staff and specialists, used to:

1. Authenticate a working session by picking a **user type** and **insurance type**, then proving
   the claim exists by entering its **کد رایانه پرونده** (computer file code) — or, when the user
   doesn't know it, falling back through an "I don't know" cascade of identifiers.
2. Collect the case's identifying data (names, national code, plate, policy number, …).
3. Capture a structured set of **photos** (car documents, license, chassis, and the four car views)
   with **anti-fraud timing validation**.
4. On finish, persist the images into a per-case folder in `storage/`, assign a **unique
   reference number**, and show a completion page stating the case is "under review by AI
   with a unique number".

Target devices: **phones, tablets, laptops** — responsive is mandatory.
Audience: insurance specialists & staff → **minimal, UX-friendly** interface
(style reference: `plan/1.png`, `plan/2.png`, `plan/3.png`).

---

## 2. Original Requirements (verbatim prompt)

> **Project Initiation**
> Initialize a persian RTL web application written in django and django templates with custom css
> and js with occasional help of tailwindcss and bootstrap libraries.
> English fonts: sans-serif / consolas. Persian fonts: Vazir / B Nazanin.
> English backend and persian frontend [with verbose names].
> Backend have multi app core. App's with "app_" prefix for their names [like app_account, app_main,
> app_core, etc]. sqlite3 database [default for dev].
> Inspiration for frontend UI/UX style: @plan/1.png, @plan/2.png, @plan/3.png → I have also put the
> code for these page in the plan folder since I said I'm looking for something just like this style wise.
> Logo: @plan/dana-logo.png. Plate num selector: @plan/plate.jpg (located as well in @plan/1.png).
> The application is designed initially [at its current version] for insurance specialists and staff.
> Minimal and UX friendly. The inspiration images above show exactly what kind of UI/UX I'm looking for.
> Responsive elements are a must. Must work on phones, tablets, laptop.
> * I will be saying some of the attributes and words in persian for those translate them
>   accordingly to neat variable names for the codebase.

> **LOGIN**
> First page is login.
> 1. First user chooses between "ورود به عنوان :": "کارشناس" or "نماینده" or "بیمه شده" or
>    "خدمات غیرحضوری".
> 2. Then the next thing user chooses is "نوع بیمه". Has two values: "بیمه بدنه" and
>    "بیمه شخص ثالث مالی". Depending on what the user selects the path they must take from now on changes.

> **USER-TYPE, BIMEH-TYPE**
> 3. The values for "کد رایانه پرونده" has a starting letter which differs depending on the user type.
>    - If user type is "کارشناس" their "کد رایانه پرونده" MUST start with the letter "p"
>      (validations must be written for this and the placeholder would show an example starting with p).
>    - If user type would be "نماینده" the exact same scenario would be true but with the letter "n".
>    - For when the user type is "بیمه شده" or "خدمات غیرحضوری" no prefix is needed (no validation rule).

> **BIMEH BADANE**
> - If "بیمه بدنه" is selected the user must first enter "کد رایانه پرونده". It's a dropdown with
>   search ability. In the dropdown list the available objects which belong to the date of TODAY
>   (only today ones must be displayed) will be displayed. If any value was yesterday or older the
>   user must enter it manually. They can also enter the first couple of characters and it would
>   search through the whole values and display the ones with those characters (contain).
> - There will also be a checkbox option saying "پلاک ماشین من عوض شده است". If the user checks
>   this part a element shown as in "plate" [inside plan/1.png] will appear below it allowing the
>   user to enter their "شماره پلاک". Otherwise [if unchecked] they can proceed forward without
>   any issues.

> **BIMEH SALES**
> - If "بیمه شخص ثالث مالی" is chosen, the user enters "کد رایانه پرونده" just like the other
>   option [same dropdown and search stuff. In fact this feature is a repeating thing with many
>   options said from now on, I will point them out tho]. But after they do, they must fill in
>   "شماره بیمه نامه" [same with "کد رایانه پرونده" with dropdown stuff].
>   Then below user must enter the following data: اسم و فامیل, کد ملی, شماره پلاک
>   (a box for each one. The dropdown feature does not apply to these ones tho).

> **IDK-BOX**
> For both "نوع بیمه" there would be a checkbox below "کد رایانه پرونده" saying "I don't know it"
> and if they check it a new box would appear below it with the same functionality of search and
> list dropdown like others. And the previous option would become disabled. Another checkbox would
> also appear for this as well like the last one "I don't know it" and this time the new box would
> be for "شماره پلاک". Again another checkbox for this as well leading to "شماره ماشین" and also
> one other for "کد ملی".
> So basically if the user checks this checkbox a new box would appear including the checkbox
> (until the last one in which should not have it) so they can fill in the information they actually
> have. It's made so if the user didn't have the value for the previous box they can fill in the
> next one.

> **IMAGE-UPLOAD**
> No matter which "نوع بیمه" is selected after the above steps they must take some pictures. In the
> frontend reference the second picture is where image uploading was handled.
> One thing I would do differently as that is when you upload images you have to confirm their upload
> which is repetitive. Since you have to click a final finish button anyway. So in our case don't put
> any confirm/cancel button for images but keep the remove uploaded image cross on each one to let
> the user remove any uploaded image [and remember not until the finish button is pressed the images
> will not be saved inside the local directory. Inside the storage folder located in the root dir].
> The image upload section would also be not just one. But instead of a big upload all images section
> there would be some parts which the user must individually upload an image of a specific thing.
> - The first thing is "پشت و رو کارت ماشین" so at least 2 pictures must be uploaded with the label
>   of the said images.
> - Next are "پشت و رو گواهینامه" at least 2 images.
> - Next "شماره شاسی ماشین".
> The user would still be able to see each one in details and discard [remove] them after being uploaded.
> * [One important note: please keep track of the exact time images are uploaded for the car images,
>   specifically "پشت و جلو و راست و چپ" and "شماره شاسی ماشین". Since we want to have a validation
>   process where the app would calculate the time difference [duration in between] of each image
>   upload and if there was more than 10 sec apart from each other the whole "پشت و جلو و راست و چپ"
>   uploading process would be canceled resulting in the already uploaded images to be discarded
>   [the calculation would be done after all images are uploaded and if the time was more than said an
>   error message would pop up and the already uploaded images would be discarded. Remember this
>   process only applies to car images that are "پشت و جلو و راست و چپ ماشین" and "شماره شاسی
>   ماشین"].
> This thing only applies to the "car images" and not the "پشت و رو کارت ماشین" and "پشت و رو
> گواهینامه" and "شماره شاسی ماشین". You don't need to calculate their time but do store their date
> time like others. If the time gap of said images when further than 10 minute a pop up message would
> say you took too long to take the pictures, please try again. And also there would be a small
> message above the first image uploading section for the car saying you only have 10 minute to take
> picture of your car so that they would know they must hurry.

> **FINISH**
> At the end of this page the text "شده در حال برسی با هوش مصنوعی با شماره یکتا می باشد" must also
> be seen clearly. As a sort of disclaimer.

> **IMAGE-SCRIPT**
> Also there will also be a python script added later that would put a watermark overlay on each
> image before they are saved. But not to worry about that yet.

> **DB**
> I will give you the list of attributes each "نوع بیمه" will have you would create a model for each
> one accordingly. The datas which would be searched through and gotten for authentication would be
> read from these models. To fill in these models I will give you excel files and you would read
> from those files and fill in the database for the search/filter/get/etc operations used for the
> backend logic.
> [Column lists for بیمه بدنه and بیمه شخص ثالث مالی — see section 5.]
> The main models for an instance must have the above attributes. Through the login and
> authentication stage the backend would read from these and allow for login. Also the excel file
> which I will give you will fill in these models.

> **FRONT-COLOR**
> * One important note: if the user chooses "بیمه بدنه" as "نوع بیمه" the website color palette
>   [from there on] will be in the tone of "green" and if they choose "بیمه شخص ثالث مالی" the
>   color would be "pink".

> **FOOTER**
> * Also anywhere you put the dana-logo.png image it must be a link to the website
>   https://www.dana-insurance.com/ + in the footer write
>   "© ۱۴۰۵ — تمامی حقوق محفوظ به بیمه دانا است" and the "بیمه دانا" part would be a hyperlink `<a>`
>   referring to the link above.

---

## 3. Reference Materials (in `plan/`)

| File | Role |
|---|---|
| `1.png` / `step1_form.html` | Step 1 (اطلاعات): step indicator, card layout, Iranian **plate component** (blue I.R. IRAN strip, digit boxes, letter select, "ایران" sub-box), name fields, document number, primary CTA. **Style reference.** |
| `2.png` / `step2_upload.html` | Step 2 (آپلود): info box with entered data + "ویرایش اطلاعات" link, dropzone + gallery/camera buttons, uploaded grid with per-image remove ×, finish bar, file-size notice. **Style + behavior reference.** |
| `3.png` / `step3_thanks.html` | Step 3 (پایان): big success icon, summary rows, image gallery, "بازگشت به شروع" CTA, secure-storage popup. **Style reference.** |
| `base.html` | Base template: RTL `<html lang="fa" dir="rtl">`, teal wave header, message alerts, footer with jalali year + linked "بیمه دانا". |
| `dana-logo.png` | Dana logo — every occurrence must be wrapped in a link to https://www.dana-insurance.com/ |
| `plate.jpg` | Real Iranian plate — visual source of the plate component (blue strip, flag, "I.R. IRAN", bolt dots). |
| `hef.co.ir.png` | Not referenced in the requirements — kept in `plan/` for the record, unused unless it gains a role later. |
| `بدنه.pdf` | Preview of the **بیمه بدنه** Excel (was .xlsx). 4 pages, 3 sample rows, 17 columns. |
| `شخص ثالث مالی.pdf` | Preview of the **بیمه شخص ثالث مالی** Excel (was .xlsx). 5 pages, 3 sample rows, 21 columns. |

The reference templates are *style* references only — the new codebase will have its own
templates (the reference flow is a single vehicle form; our flow starts with login, has
branching by insurance type, and structured upload sections).

---

## 4. Clarifying Questions & Resolutions

The clarifying questions below were prepared for the owner; answers were not collected yet, so each
is resolved with a **default** that keeps the build moving. Every default is re-listed in section 10.

| # | Question | Default adopted (⚠️ = needs confirmation) |
|---|---|---|
| C1 | Which date field makes a record a **"today"** record in the file-code dropdown? | ⚠️ **تاریخ اعلام خسارت** (claim-reported date) == today (Jalali). Rationale: the working day of a claim is when it was reported/filed. Dropdown shows only today's rows; manually typed codes are searched across **all** dates (per "yesterday or older → enter manually"). |
| C2 | Is the leading letter (p/n) of کد رایانه پرونده **stored in the DB** or input-only? | ⚠️ **Input-only prefix, stripped before lookup.** Excel codes stay pure numbers (as in the sample: `22208730`). Validation: کارشناس → must start `p` (case-insensitive); نماینده → must start `n`; بیمه شده / خدمات غیرمحضوری → no prefix (if one is typed it's accepted but stripped). Placeholders: `مثال: p12345678` / `مثال: n12345678` / `مثال: 12345678`. |
| C3 | Confirm the **"I don't know" cascade** order, and auto-fill behavior in ثالث. | ✅ **CONFIRMED:** Order: **کد رایانه پرونده → [IDK] → شماره بیمه نامه → [IDK] → شماره پلاک → [IDK] → شماره ماشین (VIN) → [IDK] → کد ملی** (last box has no IDK checkbox). Checking "نمی‌دانم" on a box disables that box and reveals the next. **No auto-fill** — the plain identity boxes (اسم و فامیل / کد ملی / شماره پلاک) must always be entered manually by the user. |
| C4 | The cascade's «شماره ماشین» (VIN) box has no VIN column in the Excel preview — how does it search? | ⚠️ The VIN box is a **plain free-text input (no search dropdown)**; its value is stored on the submission only. If the real Excel files turn out to include a VIN/chassis column, the box is promoted to the shared searchable-dropdown component without any other change. |
| C5 | Exact **image-upload sections** (the timing note mentions «پشت و جلو و راست و چپ» which the section list doesn't name)? | ✅ **CONFIRMED:** **Four sections:** S1 «پشت و رو کارت ماشین» (min 2, labeled slots «روی کارت»/«پشت کارت»), S2 «پشت و رو گواهینامه» (min 2, labeled slots), S3 «شماره شاسی ماشین» (**min 1, unlimited** — more than one chassis photo allowed), S4 «عکس‌های ماشین — پشت و جلو و راست و چپ» (4 labeled slots: جلو / پشت / راست / چپ, each min 1). **S3 joins the timing-validation group** with S4. |
| C6 | Timing rules: the prompt contradicts itself (10-sec gap vs 10-min total; chassis included vs excluded). | ✅ **CONFIRMED:** **One "car shoot" group = S3 (شاسی) + S4 (4 views)**: (a) **gap rule** — every consecutive upload within the group must be **≤ 10 seconds** apart (confirmed: 10 seconds, not a typo), checked server-side when the group is complete (re-verified on finish); on violation the **entire car group's images are discarded** and an error popup is shown. (b) **total-window rule** — first-to-last span of the group must be **≤ 10 minutes**; on violation a popup: "زمان زیادی طول کشید برای عکس‌های ماشین، لطفاً دوباره تلاش کنید." and the group is discarded for re-shoot. A permanent info banner above S3 (the first car-image section) warns about the 10-minute limit. S1/S2 are exempt from both rules (timestamps are still stored). |

Additional standing assumptions (low risk, listed for completeness):

- **A1 — No passwords.** "Login" = user-type + insurance-type selection + a file-code/identifier that
  **matches an imported record**. The selected user type is stored on the case. No Django `User`
  accounts in this version.
- **A2 — Date storage.** Jalali dates from Excel are stored **as-is (Jalali strings, e.g. `1405/04/11`)**
  for display fidelity, plus a derived **Gregorian `DateTimeField`** used for the "today" filter and
  ordering. The frontend always renders Jalali (custom template tag library in `app_core`).
- **A3 — Storage layout.** Root `storage/`. In-session uploads go to `storage/tmp/<session_id>/<section>/…`.
  On **finish** they are moved to `storage/<unique_number>/<section_slug>/<seq>_<safe_original_name>`
  (e.g. `storage/DN-1405-06-28-A1B2C3/car_views/01_front.jpg`). Temp folder of finished cases is cleaned.
- **A4 — Unique number.** Generated at finish: `DN-<JalaliDate>-<6 alphanumeric chars>`
  (e.g. `DN-1405-06-28-K7P2QX`), stored on the submission, shown large on the completion page.
- **A5 — "Under review by AI" line.** Rendered (spelling-normalized) as:
  **«پرونده شما در حال بررسی با هوش مصنوعی با شماره یکتا `DN-…` می‌باشد.»** — with the unique number
  prominent. (Original wording: «شده در حال برسی با هوش مصنوعی با شماره یکتا می باشد».)
- **A6 — Watermark.** A no-op hook `app_media.services.watermark.apply_wm(path)` sits in the finish
  pipeline; the real script plugs in later without touching other code.
- **A7 — File constraints.** `accept="image/*"`, no size cap (matching reference behavior
  «فایل‌ها با هر حجمی پذیرفته می‌شوند»), server validates content is a real image (Pillow).
- **A8 — Re-running the same code** creates a new case (submissions are per-session history); the
  records tables are reference data, not mutated by the flow.

---

## 5. Data Model (from the Excel previews)

### 5.1 `BodyInsurance` — بیمه بدنه (17 columns)

| # | Excel column (fa) | Field (en) | Type | Sample value |
|---|---|---|---|---|
| 1 | کد رایانه پرونده | `computer_code` | Char, **unique, search key** | `22208730` |
| 2 | شماره پرونده | `case_number` | Char | `1493` |
| 3 | شماره بیمه نامه | `policy_number` | Char, search key | `1404/279/9818/2102` |
| 4 | تاریخ حادثه | `accident_date` | Jalali (str) + `accident_date_greg` | `1405/04/11` |
| 5 | نوع حادثه | `accident_type` | Char | `تصادف` |
| 6 | ساعت حادثه | `accident_time` | Time | `09:30` |
| 7 | تاریخ اعلام خسارت | `claim_reported_date` | Jalali (str) + greg, **"today" filter key (⚠️ C1)** | `1405/06/19` |
| 8 | علت حادثه | `accident_cause` | Char | `عدم توجه به جلو` |
| 9 | واحد تشکیل پرونده | `case_unit` | Char | `حافظ شریاز – بیمه‌های اموال` |
| 10 | کد ملی راننده | `driver_national_code` | Char, search key | `2471117589` |
| 11 | نام راننده | `driver_name` | Char | `محمدحسین آدیبنیا` |
| 12 | گروه خودرو | `vehicle_group` | Char | `سواری` |
| 13 | سیستم خودرو | `vehicle_model` | Char | `پراید` |
| 14 | شماره پلاک | `plate_number` | Char, search key | `94س225` |
| 15 | سریال پلاک | `plate_serial` | Char | `63` |
| 16 | سال ساخت | `build_year` | Char (Jalali) | `1386` |
| 17 | ارزش خودرو | `vehicle_value` | Decimal (Toman) | `1,600,000,000` |

### 5.2 `ThirdPartyInsurance` — بیمه شخص ثالث مالی (21 columns)

| # | Excel column (fa) | Field (en) | Type | Sample value |
|---|---|---|---|---|
| 1 | کد پرونده | `computer_code` | Char, **unique, search key** | `22241847` |
| 2 | شماره پرونده | `case_number` | Char | `3379` |
| 3 | شماره بیمه نامه مقصر | `atfault_policy_number` | Char, search key | `1405/875/5029/2101` |
| 4 | سابقه ثالث مالی | `third_party_history` | Char | `دو سال عدم خسارت` |
| 5 | تاریخ اعلام خسارت | `claim_reported_date` | Jalali (str) + greg, **"today" filter key (⚠️ C1)** | `1405/06/28` |
| 6 | واحد تشکیل پرونده | `case_unit` | Char | `حافظ شریاز – بیمه‌های اموال` |
| 7 | تاریخ حادثه | `accident_date` | Jalali (str) + greg | `1405/04/24` |
| 8 | نوع گواهینامه | `license_type` | Char | `موتورسیکلت` / `پایه سه` |
| 9 | شماره گواهینامه | `license_number` | Char | `9602046006` |
| 10 | شماره پلاک | `plate_number` | Char, search key | `23582` / `94د291` |
| 11 | سریال پلاک | `plate_serial` | Char | `699` |
| 12 | گروه خودرو | `vehicle_group` | Char | `موتورسیکلت یک سیلندر` / `سواری` |
| 13 | سیستم خودرو | `vehicle_model` | Char | `یک سیلندر` / `سمند` |
| 14 | تاریخ صدور گواهینامه | `license_issue_date` | Jalali (str) + greg | `1404/12/20` |
| 15 | سال ساخت | `build_year` | Char | `1399` |
| 16 | افسر ترسیم کروکی | `sketch_officer` | Char | `کری یاریاب (کد)` |
| 17 | گزارش | `report` | Char | `اکبری صفا (کد)` |
| 18 | سری کروکی | `sketch_series` | Char | `200` |
| 19 | سریال کروکی | `sketch_serial` | Char | `4186865` |
| 20 | راننده مقصر | `atfault_driver` | Char | `حسن محمدی` |
| 21 | کد ملی مقصر | `atfault_national_code` | Char, search key | `2281225577` |
| 22* | علت حادثه | `accident_cause` | Char | `عدم توجه به جلو` |
| 22* | تعهد مالی | `financial_liability` | Decimal (Toman) | `533,333,000` |

\* 22 rows total in the file preview (the prompt lists 21 items — `تعهد مالی` and `علت حادثه`
both appear on the last page; both are included in the model).

**Normalization rules for import:** strip thousands-commas, convert Persian→Latin digits for
numeric fields (keep `plate_number`/`policy_number` mixed scripts intact after digit
normalization), parse Jalali `YYYY/MM/DD` (+ optional time), upsert keyed on `computer_code`.

### 5.3 Flow models (created by the app)

```
CaseSubmission  (app_main)
├── unique_number      Char  unique, generated at finish      A4
├── user_type          Char  choices: specialist | agent | insured | remote_service
├── insurance_type     Char  choices: body | third_party
├── record             FK → BodyInsurance | ThirdPartyInsurance (nullable — matched record)
├── computer_code      Char  as entered (letter prefix preserved for audit)
├── policy_number      Char  (third party: atfault_policy_number)
├── full_name          Char  اسم و فامیل
├── national_code      Char  کد ملی
├── plate_number       Char  شماره پلاک (plain text for ثالث / from plate component for بدنه)
├── plate_serial       Char  (if derivable from entered plate)
├── vin_number         Char  «شماره ماشین» from the cascade (C4: free text)
├── plate_changed      Bool  بدنه only: «پلاک ماشین من عوض شده است»
├── matched_by         Char  which field resolved the record: file_code|policy|plate|vin|national_code
├── created_at         DateTime (UTC)
└── finished_at        DateTime (UTC), null until finish

CaseImage  (app_media)
├── submission         FK → CaseSubmission
├── section            Char  choices: car_card_front | car_card_back | license_front |
│                                 license_back | chassis | car_front | car_back | car_right | car_left
├── file_path          Char  relative to storage/ (tmp path until finish, final path after)
├── original_name      Char
├── size_bytes         Integer
└── uploaded_at        DateTime (UTC)  ← the timestamp used by the timing validation (C6)
```

---

## 6. Architecture

### 6.1 Project layout

```
/home/user/                     # project root
├── manage.py
├── spec.md                     # this file
├── requirements.txt            # Django, Pillow, openpyxl
├── plan/                       # reference material (already populated)
├── storage/                    # final images + tmp/ (created at runtime, git-ignored)
│   ├── tmp/<session_id>/…
│   └── <unique_number>/<section_slug>/…
├── dana/                       # Django project package: settings, root urls, wsgi/asgi
├── app_core/                   # shared: base templates, jalali template tags, utils
├── app_account/                # login flow: user type + insurance type + identifier matching
├── app_records/                # Body/ThirdParty models, Excel import command, search API
├── app_main/                   # wizard (3 steps), CaseSubmission, finish orchestration
└── app_media/                  # upload endpoints, sections, timing validation, storage service, watermark hook
```

- **DB:** SQLite (default dev DB, as required).
- **Templates:** Django templates, custom CSS + vanilla JS; Tailwind/Bootstrap available as
  utility fallbacks only ("occasional help"), per the requirement.
- **Timezone:** server stores UTC; all user-facing dates are Jalali.

### 6.2 App responsibilities

| App | Responsibility |
|---|---|
| `app_core` | `base.html` (header/footer/messages/step indicator), `jalali` template tag lib (`jalali_year`, `jalali_date`, `jalali_datetime`, `persian_digits`), digit-convert utils, theme CSS tokens, Vazirmatn font assets. |
| `app_account` | The **login page** and its POST: validate user type ↔ code-prefix rule (C2), resolve the identifier (dropdown match or cascade — see 6.5), store session identity `{user_type, insurance_type, matched_record_id, identity fields}`. URL: `/` (GET) and `/login/` (POST). |
| `app_records` | Models 5.1/5.2; management command `import_records`; AJAX search endpoint(s); seed command `seed_sample_data` (imports the 3×3 sample rows from the PDF previews, with some claim dates set to today so the dropdown is demonstrable). |
| `app_main` | Step pages: `/step1-info/` (login result / info completion for badene third-party fields), `/step2-upload/`, `/step3-done/`; holds `CaseSubmission`; orchestrates finish (validations → media.finalize → unique number → redirect). |
| `app_media` | `/media-upload/` (POST per file, immediate — no confirm button), `/media-remove/<id>/`, lightbox endpoint, `services/timing.py` (C6 rules), `services/storage.py` (tmp → final move, naming), `services/watermark.py` (no-op hook, A6). |

### 6.3 Authentication model (A1)

No passwords. A session is "authenticated" when:

1. user type + insurance type are chosen, and
2. **exactly one** imported record matches the provided identifier
   (file code, or the cascade field that the user filled).

Multiple matches → show a short disambiguation list (code + policy + plate) for the user to pick
one. Zero matches → inline error «پرونده‌ای با این اطلاعات یافت نشد».
The matched record is what "allows for login" — everything else in the wizard reads from it.

### 6.4 Excel import

```
python manage.py import_records --badane  data/badane.xlsx  --satheth data/satheth.xlsx
```

- `openpyxl` reader; Persian header → field mapping table (section 5) in
  `app_records/importers.py`; tolerant of header whitespace/typos via normalization.
- Jalali `YYYY/MM/DD` → kept as string + computed Gregorian date (own converter in `app_core`,
  no external Jalali dependency needed).
- Upsert on `computer_code`; reports inserted/updated/skipped counts.
- The **actual .xlsx files arrive later**; the command is built against the preview's columns.

### 6.5 Search endpoint (shared "dropdown + search" component)

```
GET /records/search/?insurance=body|third&field=file_code|policy_number|plate_number|national_code&q=<substr>
→ { results: [ {value, label} … max 20 ] }
```

- `q` is matched with **contains** (case/accent-insensitive after digit normalization).
- Results are pre-filtered to **"today" records only** (C1: `claim_reported_date_greg` == today)
  when the widget is the file-code / policy dropdown in normal mode.
- Server-side resolution (on login POST) searches **all dates** — supporting manual entry of
  older codes, and the cascade lookup.
- Frontend: custom RTL combobox (not `<datalist>`) — debounced AJAX (250 ms), keyboard
  navigation, highlighted substring, min 2 chars to trigger (1 char for pure-digit codes).

### 6.6 Image pipeline (no confirm/cancel — immediate upload)

1. User picks/captures a file in a section slot → JS `fetch` POSTs **immediately** to
   `/media-upload/` (CSRF + section + slot). Server writes to
   `storage/tmp/<session>/<section>/…`, creates the `CaseImage` row with `uploaded_at=now(UTC)`.
   Each thumbnail gets a **remove ×** (and a zoom/lightbox on tap). No confirm/cancel buttons.
2. **Finish button** («اتمام و ساخت پوشه») → server re-validates everything (section minimums,
   car timing C6), then: `storage/tmp/<session>/…` → `storage/<unique_number>/<section_slug>/…`,
   `CaseImage.file_path` updated, temp dir removed, `finished_at` set.
3. Removing an image deletes its temp file + row instantly.
4. Session refresh safety: uploaded images persist across reloads (they're on disk + in DB);
   entering info edit keeps all uploaded images (reference behavior).

### 6.7 Timing validation (C6 — car group = chassis + 4 car views)

Constants: `CAR_IMAGE_MAX_GAP_SECONDS = 10`, `CAR_IMAGE_MAX_SPAN_MINUTES = 10`.

- Trigger A (fast feedback): when the **last required car image** is uploaded, the server checks
  the group's `uploaded_at` series; on violation → delete the group's files+rows, respond with
  `{"error": "car_group_reset"}` → JS popup with the Persian error message and clears the car slots.
- Trigger B (authoritative): the finish endpoint re-runs the same check; same consequence.
- Gap check: `max(t[i+1] - t[i]) ≤ 10s` over the ordered car-group timestamps.
- Span check: `last - first ≤ 10min`.
- Static warning banner above S3 (first car-image section):
  «⏱ فقط ۱۰ دقیقه فرصت دارید تا عکس‌های ماشین (شاسی و نمای جلو/پشت/راست/چپ) را بگیرید.»
- S1 (کارت ماشین) and S2 (گواهینامه): **no** timing checks; `uploaded_at` still stored.

### 6.8 Finish / unique number (A4)

Generated at finish, format `DN-<JJYY/MM/DD>-<6×A-Z0-9>` (uniqueness enforced in DB, retry on
collision). Shown large on step 3 + in the AI-review disclaimer sentence (A5).

### 6.9 Watermark (future, A6)

`app_media/services/watermark.py::apply_wm(src, dst) -> dst` — currently `shutil.copy`. Called in
`storage.finalize_case()` for every file. The later script replaces the body of this one function.

---

## 7. Frontend / UX

### 7.1 Design language (from the reference)

- Clean **white cards** on a very light gray-blue background; generous border-radius (14–18 px),
  soft shadow, thin borders.
- **Header**: brand teal gradient with a curved bottom edge (SVG wave), centered title + subtitle.
- **Step indicator** (3 steps): «اطلاعات — آپلود — پایان» with numbered circles, connectors that
  turn green with ✓ when done (exactly like the reference).
- Card header row: **Dana logo at top-right** (RTL) + bold title; muted description paragraph.
- Buttons: full-width primary CTA with left-pointing arrow icon on continue buttons;
  success-green finish button «✔ اتمام و ساخت پوشه».
- Info box (read-only summary of entered data) with «ویرایش اطلاعات» link.
- Persian digits everywhere (۰۱۲۳۴۵۶۷۸۹); LTR islands (`dir="ltr"`) for codes, plates, times.
- Modest motion: pop-in popups, progress bars (reference step-3 secure popup style reused for
  the "files saved" moment — 3 s auto-dismiss).

### 7.2 Color themes (FRONT-COLOR)

CSS custom properties on `<html data-theme="…">`:

| Token | `default` (login, pre-selection) | `badene` (بیمه بدنه) | `satheth` (ثالث مالی) |
|---|---|---|---|
| `--primary` | `#0f8a9d` (brand teal, as reference) | `#1f9d55` green | `#d6336c` pink |
| `--primary-dark` | `#0a6c7c` | `#157347` | `#a61e4d` |
| `--primary-soft` (fills/hover bg) | `#e6f4f6` | `#e6f4ec` | `#fbe8ef` |
| `--accent` (buttons like plate's blue) | `#004ea1` | `#146c43` | `#9c1746` |
| `--success` | `#12969e` | `#2b8a3e` | `#c2255c` |

Theme is set **when the insurance type is chosen on the login page** and persists through the rest
of the session (stored in session; applied on every render). Header gradient, CTAs, active step,
focus rings, and section badges all follow the tokens. The blue plate component keeps its
**real-world colors** (it's a physical object) in all themes.

### 7.3 Fonts & digits

- **Persian:** `Vazirmatn` (self-hosted WOFF2 in `app_core/static/fonts/`, weights 400/500/700/800)
  with fallback `'B Nazanin', 'Tahoma', sans-serif`.
- **English/latin:** system `sans-serif`; `Consolas` for code-like values (file codes, unique
  numbers, file sizes) — applied via a `.mono-ltr` utility.
- Persian digits rendered via a `to_persian` template filter / JS helper for runtime values.

### 7.4 Pages & flow

**Step 0 — Login (`/`)** — one card, three numbered blocks:
1. «ورود به عنوان:» — 4 selectable cards (radio behavior, icon + label):
   **کارشناس / نماینده / بیمه شده / خدمات غیرحضوری**.
2. «نوع بیمه» — 2 selectable cards: **بیمه بدنه** (green dot hint) / **بیمه شخص ثالث مالی**
   (pink dot hint). Selecting one **switches the theme immediately** (visual confirmation).
3. Dynamic identifier block:
   - «کد رایانه پرونده» — searchable combobox (6.5). Placeholder per user type (C2).
     Inline prefix validation for کارشناس/نماینده (live, as they type).
   - **«نمی‌دانم» cascade (C3)** below it: checking it disables the current box, slides open the
     next box with the same combobox component, each carrying its own «نمی‌دانم» checkbox —
     file code → بیمه‌نامه → پلاک → شماره ماشین (VIN, plain box per C4) → کد ملی (no checkbox).
     The user stops at the first box they *can* fill; the rest of the cascade stays closed.
   - **بدنه extra:** checkbox «پلاک ماشین من عوض شده است» → reveals the **plate component**
     (7.5). Unchecked → proceed without it.
   - **ثالث extra (after the identifier is resolved):** «شماره بیمه نامه» combobox (same
     dropdown feature) + three plain boxes: **اسم و فامیل**, **کد ملی**, **شماره پلاک**
     (auto-filled from the matched record where available — C3; always editable).
   - CTA: «ادامه به آپلود تصاویر ←» (disabled until a record is resolved).

**Step 1 — Upload (`/step2-upload/`)** — style of `2.png`:
- Info box: entered identity summary + «ویرایش اطلاعات» (returns to step 0, keeps uploads).
- Warning banner (car group, C6) above section S3.
- Four section cards (C5), each with: title, min-count badge («حداقل ۲ تصویر»), slot chips
  (labeled slots filled/empty), thumbnail grid (zoom + remove ×), two action buttons
  «انتخاب از گالری» / «گرفتن عکس با دوربین» (`capture="environment"` for phones), drag-&-drop
  on desktop. Uploads are **immediate** (no confirm/cancel), counter updates live.
- Finish bar: «آماده اتمام؟» + «✔ اتمام و ساخت پوشه».
- Footnote: «فایل‌ها با هر حجمی پذیرفته می‌شوند…» (reference text).

**Step 2 — Done (`/step3-done/`)** — style of `3.png`:
- Logo (linked), big ✓ icon, «با تشکر، پرونده با موفقیت ثبت شد!».
- **Unique number block (A4)** — large, copy-friendly, Consolas/LTR.
- **Disclaimer sentence (A5):** «پرونده شما در حال بررسی با هوش مصنوعی با شماره یکتا
  `DN-…` می‌باشد.»
- Summary rows (نام / پلاک / کد پرونده / تاریخ ثبت in Jalali) + saved-images gallery grouped
  by section (click → lightbox full size).
- «بازگشت به شروع» CTA → clears session + temp files, back to login.
- 3 s auto-dismissing "files stored securely" popup (reference behavior).

### 7.5 Key components

- **Plate component** (from `1.png`/`plate.jpg`): `dir="ltr"` bar — blue strip (flag +
  "I.R. IRAN" + bolt dots), 2 digit boxes → letter select (Persian alphabet, ۲۳ letters +
  "—" blank) → 3 digit boxes → «ایران» mini-box (2 digits, for the classic format).
  Auto-advance between boxes, backspace nav, paste support, Persian-or-Latin digit acceptance,
  normalized value = `DD-L-DDD[-II]`. Used only in the بدنه «پلاک عوض شده» branch.
- **Searchable combobox** (6.5) — single reusable component for file code / policy / plate /
  national-code cascade boxes.
- **Upload slot card**, **lightbox**, **popup/modal**, **step indicator**, **toasts** — all
  custom CSS/JS, RTL-aware.

### 7.6 Responsive rules (phone / tablet / laptop)

- Mobile-first; `clamp()` fluid typography (as in reference).
- ≤ 640 px (phone): login option cards 2×2; plate component boxes shrink (min 34 px touch
  targets) or the plate scrolls horizontally; upload grid 2 cols; step indicator compact
  (icons + current label).
- 641–1024 px (tablet): option cards 4×1 / 2×1; upload grid 3 cols; plate full width.
- ≥ 1025 px (laptop): card max-width ~760 px centered; upload grid 4–5 cols.
- Camera button order prioritizes «گرفتن عکس با دوربین» on mobile (reference order),
  gallery-first on desktop; drag-&-drop hidden on touch.
- All interactive elements ≥ 44 px touch targets; `input mode` hints (numeric) for code boxes.

### 7.7 Footer & logo (FOOTER requirement)

- Footer, every page: `© {% jalali_year %} — تمامی حقوق محفوظ به
  <a href="https://www.dana-insurance.com/" target="_blank" rel="noopener">بیمه دانا</a> است`
  (renders «© ۱۴۰۵ — …» today).
- **Every** `dana-logo.png` occurrence (login card, step cards, done page) is wrapped in a link to
  https://www.dana-insurance.com/.

---

## 7-bis. Session timeout & the global «خروج» button (v1.12)

Two additions the owner asked for in round 18: nobody stays inside the app longer
than ten minutes, and every page carries a way out.

### 7-bis.1 The ten-minute sequence

| Piece | File | What it does |
| --- | --- | --- |
| Config | `dana/settings.py` → `DANA` | `SESSION_TIMEOUT_SECONDS = 600`, `SESSION_TIMEOUT_WARN_SECONDS = 60`, `SESSION_TIMEOUT_MODE = 'idle'` — all three also read `DANA_TIMEOUT_SECONDS` / `DANA_TIMEOUT_WARN_SECONDS` / `DANA_TIMEOUT_MODE` from the environment, which makes a short demo window trivial (`DANA_TIMEOUT_SECONDS=30 python manage.py runserver`) |
| Server rule | `app_account/middleware.py` → `SessionTimeoutMiddleware` (first in `MIDDLEWARE`) | Measures the elapsed time before every request. `'idle'` counts from the last request, `'absolute'` from the login (`auth['at']`). When the time is up it calls `close_session()`: pops `auth` / `login_state` / `case`, logs a `session_timeout` row and redirects to `/?timeout=1`. Every served request stamps `auth['last_seen']`, so an active operator never gets thrown out |
| The page | `app_core/static/js/core.js` → `DANA.initTimeout()` + `base.html` (`window.DANA_TIMEOUT`) | Shows a countdown, opens the popup («مهلت نشست در حال پایان است», «ادامهٔ کار» / «خروج») 60 s before the end, refreshes the deadline with `GET /session/ping/`, and 2.5 s after reaching zero goes to `/?timeout=1` (the grace keeps the browser clock from beating the server clock) |
| The endpoint | `app_account/views.py` → `session_ping` (`/session/ping/`) | Returns `{ok, seconds, warn, remaining, mode}`; the request itself is what pushes the deadline away. Not a page view (`app_account/activity.py`) |
| The landing page | `app_account/views.py` → `login` with `?timeout=1` | Closes the session even if the browser arrived a moment early, and shows «مهلت نشست شما به پایان رسید (۱۰ دقیقه بی‌فعالیتی). برای ادامه دوباره وارد شوید.» |
| The log | `UserActivity` action `session_timeout` | «پایان خودکار نشست پس از ۱۰ دقیقه بی‌فعالیتی» with the user that was inside (migration `app_account/0004`) |

Sequence: 10 minutes pass without a request → server closes the session (or the
page, 60 s earlier, warns and counts down) → popup → «ادامهٔ کار» extends by ten
minutes, doing nothing sends the operator to the login page with the notice → a
`session_timeout` line in the activity log.

### 7-bis.2 The exit button on every page

`app_core/context_processors.py` computes `show_exit` (a username is in the
session and the page is not one of `logout`, `login*`, `session_ping`,
`step3_done`) and `base.html` renders a white pill «⏻ خروج <نام کاربری>» in the
header of every such page — the wizard's own steps keep their badge «خروج», and
the **final page keeps its own «بازگشت به شروع»**, so no page ends up with two
ways out and none is left without one.

## 7-ter. One identifier at a time & the database repair tool (v1.12)

**Identifier rule (tightened in round 18, owner request).** On the identifiers
page exactly **one** of the search keys may be filled; while one holds a value the
others are *unavailable* rather than silently ignored, and deleting the value
frees them again:

| State | «کد رایانه پرونده» | شناسه‌های «ورود با سایر اطلاعات» |
| --- | --- | --- |
| Nothing filled | enabled (its فهرست opens) | enabled |
| کد رایانه پرونده filled | enabled | disabled — the popup opens to show the reason («ابتدا مقدار آن کادر را پاک کنید») |
| an alternate identifier filled | disabled (no click, no فهرست) | the filled one stays editable so it can be **deleted**; the others are disabled |
| the value deleted (or the box removed with ✕) | enabled again | enabled again |

`DANA.syncIdentifiers()` (`app_core/static/js/core.js`) re-evaluates the state on
every keystroke/combobox pick; `MULTI_METHOD_ERROR` in `app_account/views.py` is
the server-side backstop (one identifier → continues, two → refused). The lock is
explained in-line: `#code-lock-note` under the code box and `#alt-lock-note-code`
inside the popup (`app_account/templates/account/login.html`).

**Database repair (new command).** A `db.sqlite3` that is older than the code
fails with `no such column: app_media_caseimage.saved_name`; since
`django_migrations` may already list the migration, `migrate` cannot fix it.
`python manage.py repair_db` (`app_core/management/commands/repair_db.py`)
compares the real schema with the models, adds the missing columns and reports
them (`--dry-run` to only look); old image rows keep an empty `saved_name` until
`./watermark.sh --all --rename` fills it.

## 7-quater. Configuration in `.env` & the live development override (v1.13)

**`.env`.** All configuration moved out of the code: `.env.sample` is the
documented template (every key + default + comments), `.env` is the runtime file,
and `dana/settings.py` only reads values through `dana/env.py` (a ~100-line
reader, no dependency). Precedence: environment `DANA_<KEY>` → environment
`<KEY>` → `.env` → the default in the code; an empty value in the file means
"use the default". Keys: Django basics (`SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`,
`LANGUAGE_CODE`, `TIME_ZONE`, `SQLITE_NAME`, `STATIC_URL`, `STATIC_ROOT`,
`STORAGE_ROOT`), brand links (`DANA_URL`, `HEF_URL`), case rules
(`CAR_IMAGE_MAX_GAP_SECONDS`, `CAR_IMAGE_MAX_SPAN_MINUTES`), session timeout
(`SESSION_TIMEOUT_SECONDS`, `SESSION_TIMEOUT_WARN_SECONDS`,
`SESSION_TIMEOUT_MODE`), switches (`AUTO_SYNC_EXCEL_ON_START`,
`AUTO_SYNC_ON_PAGE_VIEW`, `ACTIVITY_LOG`, `DEV_TOOLS`) and the watermark block
(`WATERMARK_*`, `WATERMARK_FALLBACK_COORDS=lat,lng`).

**Live override (development).** The page right before the upload page shows one
very small, unlabeled box in the footer holding `CAR_IMAGE_MAX_GAP_SECONDS`
(owner request). Typing a value stores it in the **session** (`app_core/dev_settings.py`,
`SESSION_KEY='dev_settings'`) and every consumer reads the effective value:
the upload banner (`app_main/views.py` → `car_max_gap`/`car_max_span`),
the identifiers page, and the «تأیید نهایی» timing check
(`app_media/views.py` → `timing.evaluate(..., gap_seconds=…, span_minutes=…)`).
Emptying the box removes the override and the `.env` value returns. Nothing is
ever written to `.env`, the box exists only when `DEV_TOOLS` is true, and the
endpoint `POST /dev/setting/` (CSRF-protected, `app_core/views.py`) validates the
key against `dev_settings.EDITABLE` and the value against min/max.

## 7-quinquies. Round 18/19 changes (v1.13)

| # | Change | Where |
| --- | --- | --- |
| 1 | The tiny footer box works on **every page** (not only the page before the upload) | `app_core/templates/base.html` (`dev_tools` / `dev_gap`) |
| 2 | No placeholder on the username box | `app_account/templates/account/login.html`, `core.js` |
| 3 | «پلاک خودرو عوض شده است» → «پلاک خودرو **تغییر کرده است**» | login template, `app_main/models.py`, `app_main/views.py` |
| 4 | Removed: «فقط یکی از دو روش قابل استفاده است …» and the plate-format hint | login template |
| 5 | Plate: «ایران» sits **above** the last two digits, digits share one baseline (`.plate-iran` is absolutely positioned, `.plate-main` has extra top padding) | `style.css` |
| 6 | The watermark now runs **automatically right before saving into the final folder**: uploads stay raw in `storage/tmp/…`, and on «اتمام» each photo is stamped into `storage/files/<unique>/<section>/` | `app_media/services/storage.py::finalize_case`, `watermark.apply_wm` |
| 7 | No fixed *manual* GPS entry — without a fix the stamp says **«No GPS Found»** (comment field too); the flow never blocks | `app_media/static/js/media.js`, `app_media/services/watermark.py` (`gps_text()`, `NO_GPS_TEXT`) |
| 8 | Metadata comment rewritten with explicit charsets so viewers show Persian: `XPComment` (UTF-16LE — Windows *Properties → Details → Comments*), `UserComment` (`UNICODE\0` + UTF-16LE), `ImageDescription` (UTF-8 bytes), JPEG `COM` | `watermark._metadata_block()` |
| 9 | `./watermark.sh --out DIR` keeps the «code,date-time» names and never overwrites a copy (`-2`, `-3`, …) | `watermark_images.py` |
| 10 | Storage browser lists the finished cases of `storage/files` in their own section | `app_media/storage_views.py`, `storage_index.html` |

## 8. Validation Summary

| Where | Rule |
|---|---|
| Login — prefix | کارشناس: code starts `p`; نماینده: starts `n` (case-insensitive, stripped for lookup — C2). Others: optional, stripped. |
| Login — match | Identifier must resolve to exactly one imported record (else error / disambiguation list). |
| Login — بدنه | «پلاک عوض شده» checked ⇒ plate component fully filled (or at least a consistent plate value) before continue. |
| Login — ثالث | بیمه‌نامه resolved + name / national code / plate non-empty (auto-fill or manual). |
| Upload — minimums | S1 ≥ 2, S2 ≥ 2, S3 ≥ 1, S4 ≥ 4 (one per labeled slot) — C5. Finish blocked with per-section Persian hints otherwise. |
| Upload — file type | Valid image (Pillow probe); original name kept alongside a safe stored name. |
| Upload — timing | Car group (S3+S4): consecutive gap ≤ 10 s AND total span ≤ 10 min; violation ⇒ group discarded + popup (C6). |
| Session | CSRF everywhere; uploads scoped to session folder; temp cleanup on finish/restart. |
| Page-view sync | The upload (info) page and the final page call `app_core.startup.sync_excel_if_changed()`: the `storage/data/*.xlsx` files are re-imported only when their signature (name, mtime, size — stored in `storage/.excel_signature.json`) changed. Replaces the manual `seed_sample_data`. Toggle: `DANA['AUTO_SYNC_ON_PAGE_VIEW']`. |
| Excel format | Layout-tolerant: header row auto-detected in the first 10 rows, columns matched **by header name** (order/colors/RTL irrelevant), unknown columns ignored, Jalali dates as `YYYY/MM/DD` (Persian digits ok), money with separators ok, empty rows skipped, file classified by name keywords. Required: the کد رایانه پرونده column. The «رمز عبور» column was removed (accounts live in the User model). |
| Activity log | `app_account.models.UserActivity` (append-only; read-only admin; newest first). Writers: `app_account/activity.py::log_activity()` / `record_login_attempt()` called from the owning views, and `app_account/middleware.py::UserActivityMiddleware` for `page_view`. Shared helpers: `app_account/utils.py` (`get_client_ip` — X-Forwarded-For aware, `truncate`), `app_account/admin_filters.py` (`DateTimeFromToFilter`). Toggle: `DANA['ACTIVITY_LOG']`. |
| Brand links | `settings.BRAND_URLS` (`DANA_URL`, `HEF_URL`) exposed by the context processor as `{{ DANA_URL }}` / `{{ HEF_URL }}`. |
| Startup sync | Reference data + login accounts are synced **after** Django is initialised — `app_core/startup.py::sync_all()` called by the custom `runserver`, `manage.py sync_data`, and `dana/wsgi.py`/`asgi.py`. Never in `AppConfig.ready()` (that queries the DB too early → `RuntimeWarning: Accessing the database during app initialization is discouraged`). Idempotent; toggles: `DANA['AUTO_SYNC_EXCEL_ON_START']`, `DANA['AUTO_SYNC_USERS_ON_START']`. |

---

## 9. Non-Goals / Future Work (explicitly out of scope for v1)

- Passwords / Django user accounts, roles beyond the 4 selected types (A1).
- Watermark logic (hook only — A6); the script arrives later.
- AI review itself (the disclaimer only states it; no AI service integration).
- Managing/persisting cases across multiple sessions of the *same* case (one case = one session).
- Excel files are **imported**, never edited by the app.

---

## 10. Open Items — need owner's confirmation (⚠️)

These are the six prepared clarifying questions; the defaults in the table below were adopted.
Reply "C3: no auto-fill" style to override any of them — each is a localized change.

1. **C1 — "Today" filter field:** default = `claim_reported_date` (تاریخ اعلام خسارت).
   Alternatives: `accident_date`, or "either date".
2. **C2 — p/n prefix storage:** default = letter is input-only, stripped before DB lookup
   (Excel codes remain pure numbers).
3. **C3 — IDK cascade:** default order file code → بیمه‌نامه → پلاک → VIN → کد ملی, with
   auto-fill of the plain identity boxes from the matched record (editable).
4. **C4 — VIN box:** default = plain free-text (no search) since the Excel preview has no VIN
   column; auto-promote to searchable if the real xlsx includes one.
5. **C5 — Upload sections:** default = 4 sections (کارت ماشین ≥2 labeled, گواهینامه ≥2 labeled,
   شاسی ×1, ماشین four views جلو/پشت/راست/چپ ×1 each).
6. **C6 — Timing rules:** default = one car group (شاسی + 4 views), 10 s max gap between
   consecutive uploads, 10 min max total span, whole group discarded on violation, 10-min warning
   banner above the first car section. **Double-check "10 seconds" is not a typo for 10 minutes**
   (one constant: `CAR_IMAGE_MAX_GAP_SECONDS`).

Also confirm: A1 (no passwords), A3 (storage layout), A4 (unique-number format), A5 (exact
disclaimer sentence).

---

## 11. Build Order (✅ completed in v1.1)

1. ✅ Project scaffold: `dana/` settings (SQLite, apps, static, `STORAGE_ROOT`), `app_core`
   (base template, jalali tags, Vazirmatn fonts, theme CSS, utilities).
2. ✅ `app_records`: models (5.1/5.2) + migrations + `import_records` (tested with a generated
   .xlsx incl. Persian digits/commas) + `seed_sample_data` + search endpoint.
3. ✅ `app_account`: login page (user type / insurance type / combobox / cascade / branches) +
   theme switching + prefix & match validation + edit-mode (`?edit=1`).
4. ✅ `app_media`: upload/remove endpoints (immediate, no confirm), section slots, timing
   service (gap ≤10 s + span ≤10 min over شاسی + 4 views, tested both ways), storage service,
   watermark no-op hook.
5. ✅ `app_main`: step pages wiring, finish orchestration (minimums → timing → unique number
   `DN-JJJJ-MM-DD-XXXXXX` → move to `storage/<unique_number>/<section>/`), done page, restart.
6. ✅ Responsive CSS (phone/tablet/laptop breakpoints) + UX polish against `plan/*.png`.

E2E verified: all login branches (direct code, p/n prefix rules, cascade by policy/plate,
not-found, ambiguous-candidate list), today-only dropdown vs. all-dates manual entry,
9-slot upload, timing violation → discard + popup, finish → done page + storage layout,
restart → full cleanup. Admin registered for all models. Note: the `jalali` PyPI package's
`jalali_to_gregorian` is buggy — a verified inverse is implemented in
`app_core/utils/jalali.py` (its `gregorian_to_jalali` is used as the source of truth).

---

## 7-sexies. Round 20 — v1.14 (کد شعبه، زیان‌دیده، bulk upload، بدون GPS)

### Owner request (verbatim, translated/summarized)

- **Watermark**: one Python module with the scripts inside it (Windows — never
  `.sh`); **remove the GPS section** — only logos + texts: تاریخ و ساعت، کد
  رایانه پرونده، شماره پرونده، شماره پلاک، شماره بیمه‌نامه، نام کاربری.
- **Info page → upload page**: drop the 3 entry fields of «بیمه شخص ثالث»
  (شماره پلاک، نام و نام خانوادگی، کدملی); delete the infos page; on the upload
  page put the کد رایانه selector + the small scrollable record panel.
  Every day a folder named the date is created in `storage/files/`. Flow:
  (1) find/enter کد رایانه **or** «ورود با سایر اطلاعات» — one identifier at a
  time; (2) the `{کد رایانه}` folder is created inside `{date}`; (3) bulk
  section **without timer** = پشت و رو گواهینامه + پشت و رو کارت ماشین with a
  confirm button at the end (**not** one-time — the one-time limit is only for
  the timer sections); (4) bulk section **with timer** (same seconds across all
  parts) = شماره شاسی، پلاک جلو، پلاک پشت; (5) car images unchanged minus
  شماره شاسی. «اضافه کردن زیان دیده» → 4 boxes (نام، نام خانوادگی، کد ملی،
  شماره ماشین/پلاک) + the same 3 sections, button again under each victim.
  مقصر images → `storage/files/{date}/{کد رایانه}`; victim images →
  `.../{کد رایانه}/{شماره پلاک}` (پلاک الزامی، نام/کدملی اختیاری). Every image
  named after its field.
- **Branch**: «کد شعبه» field on **both** bimeh models; user creation selects
  branch id(s) (multiple allowed); record lookups only show rows of the user's
  branches; the native browser back button acts like the app's back button.
- **UI**: timeout warning without the icon, shown only **15 s** before timeout;
  remove the white pixels right of the plate component.
- **Folders**: each ثبت پرونده is assigned to the user who completed it; the
  folders page only lists folders **ending with the logged-in username**.
- **Login**: remove «بیمه شده» and «خدمات غیرحضوری» entirely; no user-type
  buttons — the form is immediate; type from the username prefix (`p` →
  کارشناس, «د» → نماینده; no validation except an unknown prefix).

### Decisions taken (owner's “continue”)

- نماینده prefix = «د» **and** legacy `n`/`d` (old seeded usernames). Any other
  first letter is the only login error.
- Folder names carry the owner: `storage/files/{Jalali YYYY-MM-DD}/{کد
  رایانه}-{username}/`; a victim subfolder is `{شماره پلاک}/`; file names are
  the section keys (`car_card_front.jpg`, `chassis_number-2.jpg`, …).
- Group confirm: `POST /media/confirm-group/` with `group=group_docs |
  group_plates | group_car` + `party` (empty = مقصر). `group_docs` is
  repeatable (`docs_confirmed_at` refreshed on every press); the timed groups
  are one-time (`plates_confirmed`, `car_confirmed`) and a timing violation
  discards the group + resets its flags (`car_group_reset`).
- Endpoints: `POST /media/upload/` (`section`, `party`, `image` — immediate),
  `POST /media/remove/<id>/`, `GET /media/serve/<id>/`, `POST /case/resolve/`
  (finder), `POST /victim/add/` (JSON, returns the rendered victim block),
  `POST /victim/remove/`, `POST /finish/`, `GET /restart/`.
- `UserProfile.branches` (M2M → `records.Branch`); `search_records_scoped`
  takes `branch_codes=None` for unrestricted; users without branches are
  unrestricted; `branch_code` on both insurance models comes from the Excel's
  «کد شعبه» column (plus a manual admin field).
- Watermark CLI: `python -m app_media.services.watermark [--all|--case
  CODE|--section KEY|--path P] [--force] [--out DIR] [--comment-only]
  [--dry-run] [--limit N]`; `WatermarkInfo.from_submission(submission,
  username=, party=, captured_at=)`.
- Browser back: `context_processors.BACK_URLS` + `window.DANA_BACK` in
  `base.html`; `history.replaceState` rewrites the history entry so Back goes
  to the app's own previous step.
- Folders page: case folders are listed per date folder, filtered by
  `name.endswith('-' + username)` **and** the DB owner (`completed_username` /
  `auth_username`); direct URL access to someone else's case folder 404s.

## 7-septies. Round 21 — v1.14.1 (only کد رایانه, simple watermark at finalization)

Owner request (summarized): remove the information page (the second page) —
only «کد رایانه» is entered and it already lives in the upload page (keep only
that one); remove the footer comment block that shows on the page (keep only
the timer number input — its visibility is a bug, fix it); the watermark is
still not working — when the upload is finalized the watermark program must be
activated; write a **second** watermark and use it: **only کد رایانه**, simple
plain text, no styling.

Decisions taken:

- The نوع بیمه second page is removed; the insurance type is auto-detected
  from the found record (`resolve_record` searches both tables; the same code
  in both → candidate pick list `body:<pk>` / `third:<pk>`). Login goes
  straight to `/step2-upload/`; `/login/` shows the signed-in panel as the
  Back-button target.
- «ورود با سایر اطلاعات» + its identifier boxes are removed («I only enter کد
  رایانه»). The finder keeps: the کد رایانه combobox, the scrollable record
  panel (auto insurance in `records/details` & `records/search`), the plate
  branch (بدنه), and the candidates list.
- Footer: the multi-line `{# … #}` block was rendered as text (Django comment
  tags do not span lines) — deleted; only the `dev-gap-input` number input
  remains.
- Watermark: `simple_overlay` / `simple_watermark_image` /
  `simple_watermark_file` draw **only the code** (plain white text, thin dark
  stroke, configured corner). `run_simple_for_submission(submission)` stamps
  every photo at `POST /finish/` and sets `CaseImage.watermarked_at`. The CLI
  gets `--simple`; uploads store the raw file (no stamp at upload time).

## 7-octies. Round 22 — v1.15 (the نوع بیمه page is back, plate widget, no duplicates)

Owner feedback (six points) and the decisions taken:

- **«The second page» clarified**: the standalone «یافتن پرونده» screen must
  not exist — but the «انتخاب نوع بیمه» page is **required** ("after selecting
  bimeh type you go directly to the upload page"). Round 21 wrongly deleted
  it; v1.15 restores the stage-2 login card (`insurance_type` radio cards →
  `POST /login/ stage=2` → `/step2-upload/`). The upload page itself holds the
  **کد رایانه entry + the insurance details table** («only keep the one in the
  upload page»); entering the code opens the upload sections on that same page
  (`/case/resolve/` → redirect `/step2-upload/`). `resolve_record(...,
  insurance=chosen)` searches the **selected table first**, the other table
  only as fallback. Back-button target of `/step2-upload/` = `/login/?stage=2`.
- **Only one add-victim button**: the per-victim `.victim-add-trigger` in
  `_victim_block.html` is removed; the bottom `#victim-add-box` trigger hides
  while the form is open (`#add-victim-btn` ↔ `#victim-form`).
- **Plate template in the victim form**: `#vf_plate_number` text input replaced
  by the plate component (`#vf-plate`, slots `vf_plate_d1…vf_plate_ir2`).
  `DANA.composePlate` reads the slots in DOM order and builds
  `«94س225»`/`«94س225-21»` (same format as `build_plate_value`/`plate_slots`);
  `DANA.initPlate` now wires **every** `.plate` on the page.
- **No success popups except timed sections**: `confirm-group` success shows a
  `DANA.toast` for `group_docs` and keeps `DANA.popup` for `group_plates` /
  `group_car` ("unless the section has timer"). The done-page popup
  (`#secure-popup-overlay` — «فایل در چندین مکان امن ذخیره شده است») is removed.
- **No duplicate files after finalize**: (1) `save_case_image` **moves** the
  staged `*.upload` into place (`os.replace`, never copy+unlink); (2) every
  field except `car_shots` is a single-photo field — a re-upload **replaces**
  the previous photo (file + row), so no `*-2` copies; (3) `_atomic_put` in
  `watermark.py` retries the scratch move and always removes `*.wm-tmp`;
  (4) `run_simple_for_submission` sweeps any stray `*.upload`/`*.wm-tmp` in the
  case folder. After «اتمام و ساخت پوشه» the folder holds exactly one file per
  photo, each stamped with the plain کد رایانه watermark.


## 7-novies. Round 23 — v1.16 (statics/ + templates/ consolidation; viewer)

**Folders.** All static sources live in `statics/{css, js, font, img}`;
`collectstatic` merges generated output (Django admin) into `statics/admin/`
(STATIC_ROOT = `statics`, STATIC_URL = `/static/`). All templates live in the
root `templates/` folder under their namespaced names (`base.html`,
`account/login.html`, `main/*`, `media/*`) and are found through
`TEMPLATES['DIRS']`. Per-app `static/`/`templates/` folders no longer exist;
template names and `{% static %}` paths are unchanged.

**Cache-busting.** Asset URLs are `…?v={{ STATIC_VERSION }}` where
`STATIC_VERSION` (settings, env-overridable) is the single source of truth —
`1.16` for this round. Hardcoded `?v=` strings are banned.

**Image viewer (last page).** Gallery elements carry `data-lightbox`;
`core.js` binds a click handler per element *and* keeps the document-level
delegate (covers dynamically created thumbnails, e.g. upload-page thumbs).
The viewer refuses to stack (one overlay at a time), shows a load/error
state («نمایش تصویر ممکن نشد» on failure), closes on ✕ / Esc / backdrop
click, and the position uses `inset: 0` with a `top/right/bottom/left`
fallback. `media_serve` maps extensions explicitly to `image/*` content
types (`.jpg/.jpeg/.jfif` → `image/jpeg` etc.) so browsers always display
the photo instead of downloading it.

**Leftovers removed.** `P0.html` (saved snapshot of the pre-v1.6 «مرحله ۱ —
اطلاعات» page) and `pf.txt` (a curl cookie jar with expired tokens) are
deleted; `staticfiles/` (stale collectstatic snapshot) is deleted and
ignored along with `statics/admin/` (regenerated by collectstatic).


## 7-decies. Round 24 — v1.17 (upload layout + timing-cancel + watermark)

**Popups.** The only upload popup is the timing-cancel error («زمان زیادی طول
کشید!»). Group confirms (docs and timed alike) finish with a toast. The popup
button closes the dialog without navigating (no `#` history entries — those
made the browser Back button jump wizard steps).

**Timing-cancel.** `car_group_reset` removes **only** the cancelled group's
photos (server-side `discard_group` is group-scoped; the client drops just
those thumbnails) and the user stays on `/step2-upload/` — no reload, no
redirect. The upload page renders Django `messages` so finish-time timing
errors are visible.

**Layout.** The information section and the image sections are separated by a
labeled divider. Single-photo fields render as compact grid cells
(`.slot-grid`/`.slot-single`, one `.slot-grid` per group, `:empty` hidden);
the bulk field (`MULTI_PHOTO_SECTIONS`) keeps the wide `.slot-bulk` row. The
victim plate widget is centered (`#victim-form .plate-wrapper`).

**Watermark.** Finalize stamps the plain code text on every photo (in place);
`media_serve` sends `Cache-Control: private, no-store, max-age=0` so the
stamped file is what the browser displays. `simple_overlay` verifies the text
rendered (non-empty layer) and falls back to `ImageFont.load_default(size)`;
`run_simple_for_submission` retries a degraded save and records failures in
the activity log (`watermark_problem`) — never silent.

**Case re-attach.** `resolve_case` reuses the same user's unfinished
`CaseSubmission` for the same record when the session was lost, instead of
creating a duplicate and orphaning the photos.

## 7-undecies. Round 25 — v1.18 (static group texts, watermark v2, optional QR)

**Static texts.** The three group titles/banners of the upload page
(`_party_groups.html`) are literal HTML per group (`{% if g.id == 'group_docs'…%}`),
so the owner can edit them in the template; only `{{ car_max_gap|to_fa }}` /
`{{ car_max_span|to_fa }}` stay dynamic. `GROUPS` in `constants.py` remains the
fallback (the `{% else %}` branch) and the source of the error messages.

**Watermark v2.** `simple_overlay` accepts a fact dict
(`code` / `case_number` / `username` / `at` / `base_url`) or a plain string
(CLI compatibility) and renders «کد رایانه / شماره پرونده / نام کاربری /
تاریخ و ساعت» (Jalali via `app_core.templatetags.jalali_tags.jalali_datetime_of`,
Persian digits) right-aligned above the two logos (`DEFAULTS['LOGOS']`), with
the v1.17 stroke style, font fallback and `SIMPLE_POSITION` handling kept.
`run_simple_for_submission(submission, base_url=None)` builds the dict from the
submission + record; `finish` passes `request.build_absolute_uri('/')`, with
`settings.PUBLIC_BASE_URL` as the command-line fallback. The pipeline is
unchanged: finalize-time, in-place, only stamped files remain, `media_serve`
no-store.

**Optional QR (fail-safe).** Left of the text block, a QR encoding
`reverse('wm_info') + ?code&case&user&at` is stamped via `_qr_image` — a
guarded `import qrcode` (`qrcode[pil]`, declared in `requirements.txt`) and a
total catch both inside `_qr_image` and at the call site: any failure degrades
to “no QR”, never to a broken text watermark. No base URL → no QR. The public
anonymous `wm_info` view (`app_core`, `/wm-info/`, template
`templates/core/wm_info.html`) renders the four parameters and the two logos.

## 7-duodecies. Round 26 — v1.19 (proportional stamp, values only, sharp re-encode)

**Why.** Owner feedback on the v1.18 stamp (two screenshots): (1) on small
resolutions the watermark covered too much of the photo, (2) small photos
lost quality, (3) the Persian labels were unreadable — remove them.

**Root cause of (3).** The installed Pillow wheels build without libraqm
(`PIL.features.check('raqm')` is false), so Persian letters are drawn as
disconnected isolated glyphs. Values (ASCII digits, Latin usernames, Persian
digits) need no shaping and render fine. `simple_overlay` therefore stamps
`_stamp_lines(info)` = the four **values** only, in the order کد رایانه /
شماره پرونده / نام کاربری / تاریخ و ساعت. (The `/wm-info/` page keeps the
labelled table — HTML handles Persian correctly.)

**Proportional sizing (1).** `font_size = clamp(min(w, h) × 0.034 … )` capped
so the whole block stays under `MAX_HEIGHT_FRACTION` (0.38) of the photo
height and floored at 5 px / capped at 64 px. Logos (`1.6 × font`), margins
and the QR all derive from it: 230×110 → ~35 % height share, 1280×960 →
~25 %, 4000×3000 → ~16 %.

**Crisp text + sharp photos (2).** The stamp block is drawn on its own
canvas at 2× supersampling and downscaled with LANCZOS (smooth strokes at
small sizes); the QR is composited after the downscale so its modules stay
geometrically sharp. `simple_watermark_file` now saves JPEG with
`quality=95, subsampling=0` (4:4:4) — PSNR of the re-encode ≈ 48 dB vs the
old ≈ 35 dB. The pipeline itself is untouched (finalize-time, in-place,
only stamped files remain, `media_serve` no-store).

**QR policy.** `_qr_image` is only called when the block (and thus the QR)
is at least `QR_MIN_SIDE` (88 px) — below that the QR is skipped entirely
(unscannable + saves space). `_wm_info_url` converts Persian digits to ASCII
(`app_core.utils.digits.to_en`) so the URL — and the QR density — stays
small. All v1.18 fail-safe guarantees remain.

**QR diagnostics (v1.19.1).** A missing `qrcode` package (or a QR render
failure) is no longer silent: `_qr_image` writes a `logger.warning` naming the
cause and the fix (`pip install "qrcode[pil]"`). The stamp is unaffected —
the QR is optional by design; the warning only explains its absence.

## 7-terdecies. Round 27 — v1.20 (custom text + .env toggles + Persian joining)

**Custom text.** `WATERMARK_CUSTOM_TEXT` (`.env` → `settings.WATERMARK
['CUSTOM_TEXT']`) is appended as a fifth stamped line under the four values
(`_stamp_lines(info, cfg)`); empty means nothing is added.
`WATERMARK_CUSTOM_TEXT_ENABLED` (default true) is the on/off toggle — false
removes the line even if text is set. `WATERMARK_QR_ENABLED` (default true)
switches the QR code off entirely; the text watermark is unaffected. All three
flow through the existing `settings.WATERMARK` → `config()` channel, so the
CLI honours them as well.

**Persian letter joining (v1.20).** The label garbling of v1.18 was Pillow's
missing libraqm: Arabic-script letters draw as disconnected isolated glyphs.
`_shape_text` now runs Arabic text through `arabic-reshaper` (presentation
forms) + `python-bidi` (visual reordering) before drawing — Pillow renders
those codepoints as correctly joined text without raqm. Strings without
Arabic-script letters (Latin, digits, Persian digits) pass through untouched,
and both packages are guarded: if absent or a call fails, the original string
is drawn (degraded but never broken). The four-value layout of v1.19 is
unchanged — labels stay off by owner instruction; shaping powers the custom
text (and Persian usernames, if any).
