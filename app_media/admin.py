from django.contrib import admin

from .models import CaseImage


@admin.register(CaseImage)
class CaseImageAdmin(admin.ModelAdmin):
    list_display = ('pk', 'submission', 'section', 'original_name', 'size_bytes', 'uploaded_at')
    list_filter = ('section',)
