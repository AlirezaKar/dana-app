from django.contrib import admin

from .models import BodyInsurance, Branch, ThirdPartyInsurance


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('code', 'title')
    search_fields = ('code', 'title')


@admin.register(BodyInsurance)
class BodyInsuranceAdmin(admin.ModelAdmin):
    list_display = ('computer_code', 'case_number', 'branch_code', 'plate_number',
                    'driver_name', 'claim_reported_date', 'accident_date')
    list_filter = ('branch_code',)
    search_fields = ('computer_code', 'case_number', 'policy_number', 'plate_number',
                     'driver_national_code', 'driver_name')


@admin.register(ThirdPartyInsurance)
class ThirdPartyInsuranceAdmin(admin.ModelAdmin):
    list_display = ('computer_code', 'case_number', 'branch_code', 'plate_number',
                    'atfault_driver', 'claim_reported_date', 'accident_date')
    list_filter = ('branch_code',)
    search_fields = ('computer_code', 'case_number', 'atfault_policy_number', 'plate_number',
                     'atfault_national_code', 'atfault_driver')
