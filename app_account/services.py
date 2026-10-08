"""Login services — the **User** model is the single source of authentication.

The accounts live in Django's ``auth.User`` + ``app_account.UserProfile`` only:
the insurance record tables are never read for logging in. A username is just a
name that follows the user-type prefix rule (v1.14 — **the type is derived from
the prefix**: کارشناس → ``p…``, نماینده → ``د…`` (or the legacy ``n…``/``d…``));
any other prefix is refused and nothing else is validated on the login.

The password is optional per account:
  * password set  → a normal password field is required (hashed with Django's hashers)
  * password off  → the account has no usable password; the user signs in with the
                    username alone (``user.set_unusable_password()``)
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction

from app_core.constants import user_type_from_username
from app_core.utils.digits import to_en
from app_core.utils.usernames import normalize_username, username_error

from .models import UserProfile

User = get_user_model()


# ------------------------------------------------------------------ lookups
def find_user(username):
    """Case-insensitive lookup of an active account."""
    name = normalize_username(username)
    if not name:
        return None
    return User.objects.filter(username__iexact=name, is_active=True).first()


def account_needs_password(username):
    """True when the account exists and has a usable (enabled) password."""
    user = find_user(username)
    return bool(user and user.has_usable_password())


# --------------------------------------------------------------------- auth
def authenticate_login_user(username_input, password_input):
    """Authenticate against the User model (v1.14 — the type comes from the prefix).

    Returns ``(profile, username, error)``. The caller enters the system as
    «کارشناس» / «نماینده» according to the first letter of the username; the
    **only** prefix validation is an error for any other first letter.
    """
    name = normalize_username(username_input)
    password = to_en(password_input or '').strip()

    if not name:
        return None, name, 'نام کاربری را وارد کنید.'
    derived = user_type_from_username(name)
    if derived is None:
        return None, name, ('نام کاربری باید با حرف «p» (کارشناس) یا «د» (نماینده) '
                            'شروع شود.')

    user = find_user(name)
    if user is None:
        return None, name, 'کاربری با این نام کاربری یافت نشد.'

    profile = getattr(user, 'profile', None)
    if profile is None:
        return None, name, ('برای این حساب نوع کاربری ثبت نشده است؛ از پنل مدیریت، کاربر سامانه را '
                            'کامل کنید.')

    if user.has_usable_password():
        if not password:
            return None, name, 'رمز عبور را وارد کنید.'
        if not user.check_password(password):
            return None, name, 'رمز عبور نادرست است.'
    # no usable password → the account signs in with the username alone

    return profile, name, None


# ---------------------------------------------------------------- management
def create_login_user(username, password=None, user_type='specialist',
                      display_name='', email='', is_system=False):
    """Create a login account, or update an existing one.

    ``password=None``/``''`` → the account gets **no password** (login without one).
    Returns ``(profile, created)``.
    """
    name = normalize_username(username)
    err = username_error(name, user_type)
    if err:
        raise ValueError(err)

    with transaction.atomic():
        user, created = User.objects.get_or_create(username=name, defaults={'email': email})
        if email and user.email != email:
            user.email = email
        if password:
            user.password = make_password(to_en(password).strip())
        elif created:
            user.set_unusable_password()
        user.is_active = True
        user.save()

        profile, _ = UserProfile.objects.update_or_create(
            user=user,
            defaults={'user_type': user_type, 'display_name': display_name,
                      'is_system': is_system})
        profile.full_clean(exclude=['created_at'])
    return profile, created


def set_account_password(username, password=None):
    """Enable (set) or disable (``None``) the password of an account."""
    user = find_user(username)
    if user is None:
        raise ValueError('کاربری با این نام کاربری یافت نشد.')
    if password:
        user.set_password(to_en(password).strip())
    else:
        user.set_unusable_password()
    user.save()
    return user
