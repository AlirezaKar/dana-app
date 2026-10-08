"""Admin list filters shared by the activity-log admins (spec.md v1.6).

``DateTimeFromToFilter`` gives the «امروز / دیروز / ۷ روز / ۳۰ روز» presets used
next to ``("created_at", admin.DateFieldListFilter)`` in the admin ``list_filter``.
"""
from django.contrib import admin
from django.utils import timezone


class DateTimeFromToFilter(admin.SimpleListFilter):
    title = 'بازهٔ زمانی'
    parameter_name = 'range'

    def lookups(self, request, model_admin):
        return (
            ('today', 'امروز'),
            ('yesterday', 'دیروز'),
            ('7days', '۷ روز گذشته'),
            ('30days', '۳۰ روز گذشته'),
            ('not_today', 'غیر از امروز'),
        )

    def queryset(self, request, queryset):
        from app_core.utils.jalali import TEHRAN

        now = timezone.now().astimezone(TEHRAN)
        start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        value = self.value()

        if value == 'today':
            return queryset.filter(created_at__gte=start_today)
        if value == 'yesterday':
            start_yesterday = start_today - timezone.timedelta(days=1)
            return queryset.filter(created_at__gte=start_yesterday, created_at__lt=start_today)
        if value == '7days':
            return queryset.filter(created_at__gte=start_today - timezone.timedelta(days=6))
        if value == '30days':
            return queryset.filter(created_at__gte=start_today - timezone.timedelta(days=29))
        if value == 'not_today':
            return queryset.filter(created_at__lt=start_today)
        return queryset
