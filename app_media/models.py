"""CaseImage — every uploaded case photo (stored straight into its final folder).

v1.14: the GPS columns are gone (the watermark keeps only logos + text), the
file is named **after the field it was uploaded for** (``car_card_front.jpg``,
``license_back.jpg``, ``chassis_number.jpg``, …) and a photo either belongs to
مقصر (``party is NULL``) or to one :class:`app_main.DamagedParty` (زیان‌دیده).
"""
from django.db import models

from .constants import SECTION_CHOICES


class CaseImage(models.Model):
    submission = models.ForeignKey(
        'app_main.CaseSubmission', on_delete=models.CASCADE, related_name='images')
    party = models.ForeignKey(
        'app_main.DamagedParty', on_delete=models.CASCADE, related_name='images',
        null=True, blank=True, verbose_name='زیان‌دیده',
        help_text='خالی = تصاویر «مقصر»؛ پر = تصاویر همان زیان‌دیده.')
    section = models.CharField('بخش تصویر', max_length=32, choices=SECTION_CHOICES)
    image_path = models.CharField('مسیر تصویر (نسبت به storage/)', max_length=300)
    original_name = models.CharField('نام اصلی فایل', max_length=255)
    saved_name = models.CharField(
        'نام فایل ذخیره‌شده', max_length=255, blank=True,
        help_text='نام فیلدی که تصویر برای آن بارگذاری شده (مثال: car_card_front.jpg)')
    size_bytes = models.PositiveIntegerField('حجم (بایت)', default=0)
    uploaded_at = models.DateTimeField(
        'زمان بارگذاری', auto_now_add=True,
        help_text='Exact server (UTC) upload time — used by the group timing validation.')

    watermarked_at = models.DateTimeField(
        'زمان درج واترمارک', null=True, blank=True,
        help_text='Set when the watermark stamp was burned into the saved file.')

    class Meta:
        verbose_name = 'تصویر پرونده'
        verbose_name_plural = 'تصاویر پرونده'
        ordering = ['uploaded_at']

    def __str__(self):
        return f'{self.section}:{self.original_name}'
