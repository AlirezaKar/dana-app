from django.contrib import admin

from .models import CaseSubmission, DamagedParty


class DamagedPartyInline(admin.TabularInline):
    model = DamagedParty
    extra = 0


@admin.register(CaseSubmission)
class CaseSubmissionAdmin(admin.ModelAdmin):
    list_display = ('pk', 'unique_number', 'auth_username', 'completed_username',
                    'user_type', 'insurance_type', 'matched_by',
                    'created_at', 'finished_at')
    search_fields = ('unique_number', 'entered_file_code', 'entered_national_code',
                     'entered_plate_number', 'plate_value', 'auth_username',
                     'completed_username')
    list_filter = ('user_type', 'insurance_type', 'matched_by')
    inlines = [DamagedPartyInline]
