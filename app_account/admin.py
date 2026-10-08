"""Admin for the login accounts (User + UserProfile with نوع کاربری).

The کاربر سامانه (``UserProfile``) lives inside the User form as an inline, so a
user and its نوع کاربری are created in **one step**. Django validates the inline
*before* the new parent user exists, therefore the prefix rule is checked by the
inline formset below (which reads the username from the parent form) instead of by
``UserProfile.clean()`` alone.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import User
from django.forms.models import BaseInlineFormSet
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from app_core.utils.usernames import username_error

from .admin_filters import DateTimeFromToFilter
from .models import UserActivity, UserProfile


class UserProfileInlineFormSet(BaseInlineFormSet):
    """Validate the profile rows against the username typed in the parent User form."""

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        # «add» view: the parent user is not saved yet, so its username lives in POST.
        # «change» view: the parent user already exists.
        username = (getattr(self.instance, 'username', '') or ''
                    or (self.data.get('username') if hasattr(self, 'data') else '') or '')
        if not hasattr(self, 'data'):
            return

        for form in self.forms:
            cleaned = getattr(form, 'cleaned_data', None)
            if not cleaned or cleaned.get('DELETE'):
                continue
            user_type = cleaned.get('user_type')
            if not user_type:
                continue
            err = username_error(username, user_type)
            if err:
                form.add_error('user_type', err)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    formset = UserProfileInlineFormSet
    can_delete = False
    extra = 1
    max_num = 1
    verbose_name_plural = 'کاربر سامانه (نوع کاربری + شعبه‌ها)'
    readonly_fields = ('login_attempt_count', 'page_view_count', 'created_at')
    filter_horizontal = ('branches',)


class UserAdmin(DjangoUserAdmin):
    inlines = [UserProfileInline]
    readonly_fields = ('recent_activity',)
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('فعالیت‌های اخیر', {'fields': ('recent_activity',),
                             'description': 'آخرین ۲۰ فعالیت ثبت‌شدهٔ این کاربر (فقط خواندنی).'}),
    )

    @admin.display(description='آخرین فعالیت‌ها')
    def recent_activity(self, obj):
        """Bounded, read-only preview of the user's log + link to the full list."""
        if obj is None or not obj.pk:
            return 'پس از ساخت کاربر نمایش داده می‌شود.'
        rows = UserActivity.objects.filter(user=obj).order_by('-created_at')[:20]
        if not rows:
            return 'فعالیتی ثبت نشده است.'
        items = format_html_join(
            '', '<li style="margin:2px 0"><span style="color:#718096">{}</span> — '
                '<b>{}</b> — <span style="color:#4a5568">{}</span></li>',
            ((row.created_at.strftime('%Y/%m/%d %H:%M'), row.get_action_display(),
              (row.object_label or row.description or '')[:70]) for row in rows))
        url = reverse('admin:app_account_useractivity_changelist') + f'?q={obj.get_username()}'
        return format_html(
            '<ul style="margin:0;padding-inline-start:18px">{}</ul>'
            '<p style="margin:8px 0 0"><a href="{}">مشاهدهٔ همهٔ فعالیت‌های این کاربر</a></p>',
            items, url)

    @admin.display(description='نوع کاربری')
    def user_type(self, obj):
        profile = getattr(obj, 'profile', None)
        return profile.get_user_type_display() if profile else '—'

    @admin.display(description='نام نمایشی')
    def name(self, obj):
        profile = getattr(obj, 'profile', None)
        return (profile.display_name if profile else '') or '—'

    @admin.display(description='رمز عبور')
    def password_state(self, obj):
        return 'فعال' if obj.has_usable_password() else 'غیرفعال (ورود بدون رمز)'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('username', 'user_type', 'display_name', 'password_enabled',
                    'login_attempt_count', 'page_view_count', 'is_system', 'created_at')
    list_filter = ('user_type', 'is_system')
    search_fields = ('user__username', 'display_name')
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user',)
    filter_horizontal = ('branches',)


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass
admin.site.register(User, UserAdmin)


@admin.register(UserActivity)
class UserActivityAdmin(admin.ModelAdmin):
    """Strictly read-only activity log: no add, no change, no delete."""

    list_display = ('created_at', 'username_label', 'user_type_display', 'action_badge',
                    'description', 'object_label', 'short_path', 'ip_address')
    list_filter = ('action', DateTimeFromToFilter, ('created_at', admin.DateFieldListFilter),
                   'user_type')
    date_hierarchy = 'created_at'
    search_fields = ('username_label', 'description', 'object_label', 'path',
                     'ip_address', 'user__username')
    readonly_fields = ('user', 'username_label', 'user_type', 'action', 'description',
                       'object_label', 'path', 'url_name', 'page_label', 'method',
                       'ip_address', 'user_agent', 'created_at')
    ordering = ('-created_at',)
    list_per_page = 50
    fieldsets = (
        ('کاربر', {'fields': ('user', 'username_label', 'user_type', 'ip_address',
                              'user_agent')}),
        ('فعالیت', {'fields': ('action', 'description', 'object_label', 'created_at')}),
        ('درخواست', {'fields': ('path', 'url_name', 'page_label', 'method')}),
    )

    # ---- read-only enforcement ------------------------------------------
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_model_perms(self, request):
        """Show the log in the admin index (view permission is kept)."""
        return {'view': True}

    # ---- display helpers -------------------------------------------------
    ACTION_COLORS = {
        'login_success': '#1f9d55',
        'logout': '#6c757d',
        'login_failed': '#c0392b',
        'page_view': '#0f8a9d',
        'image_upload': '#2b6cb0',
        'image_remove': '#b7791f',
        'car_confirm': '#1f9d55',
        'finish': '#1f9d55',
        'record_match': '#5a3ea8',
        'insurance_select': '#5a3ea8',
        'case_edit': '#b7791f',
        'restart': '#6c757d',
    }

    @admin.display(description='نوع فعالیت', ordering='action')
    def action_badge(self, obj):
        color = self.ACTION_COLORS.get(obj.action, '#4a5568')
        return format_html(
            '<span style="display:inline-block;padding:2px 10px;border-radius:999px;'
            'background:{}1a;color:{};font-weight:700;white-space:nowrap">{}</span>',
            color, color, obj.get_action_display())

    @admin.display(description='نوع کاربری', ordering='user_type')
    def user_type_display(self, obj):
        return obj.get_user_type_display() or '—'

    @admin.display(description='مسیر')
    def short_path(self, obj):
        return (obj.path or '—')[:60]
