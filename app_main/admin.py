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
    # v1.21 — the case data lives in the referenced Excel rows; only the values
    # the user really enters are searched here.
    search_fields = ('unique_number', 'entered_file_code', 'plate_value', 'plate_serial',
                     'record__computer_code', 'record_third__computer_code',
                     'record__plate_number', 'record_third__plate_number',
                     'auth_username', 'completed_username')
    list_filter = ('user_type', 'insurance_type', 'matched_by')
    inlines = [DamagedPartyInline]
