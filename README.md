# DANA Insurance

Private Persian RTL application for insurance case registration, image uploads,
and watermarking. Built with Django, Pillow, and SQLite.

## Quick start

Requires Python 3.10+.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.sample .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 0.0.0.0:8000
```

Open `http://localhost:8000/`; staff administration is at `/admin/`.

## Configuration and operation

- Set secrets, allowed hosts, storage paths, and feature flags in `.env`;
  see `.env.sample`. Never commit credentials or customer data.
- Place reference Excel files in `storage/data/`, then run
  `python manage.py sync_data` to import records and accounts.
- Uploaded images live in `storage/files/`. Back up storage and the database.
- The storage folder browser's **manual watermark stamp** button overwrites
  images recursively after confirmation. It runs only when clicked; repeat runs
  stamp again. Back up originals first. Existing finalization behavior is unchanged.
- Production: configure `DEBUG=False`, a strong `SECRET_KEY`, `ALLOWED_HOSTS`,
  and HTTPS, then run `python manage.py serve --collectstatic` behind TLS.

## Development

```bash
python manage.py check
python manage.py test
```

See `spec.md` for requirements. Report issues and propose changes only through
this private repository, with the owner's authorization.

## License and access

Proprietary; all rights reserved. See [LICENSE](LICENSE). No public use,
redistribution, modification, or forking is granted.

Repository access is controlled by GitHub settings, not this license: keep the
repository private, limit collaborators, and disable private-repository forking
where organization policy permits. Authorized administrators can still access
and manage it; a license cannot make source technically unviewable.
