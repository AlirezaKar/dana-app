"""v1.21 — the name of a branch is its code.

Existing rows keep whatever title they had; this brings every one of them in
line with its ``code`` (the Excel column is the key, so the two must agree).
"""
from django.db import migrations


def title_from_code(apps, schema_editor):
    Branch = apps.get_model('app_records', 'Branch')
    for branch in Branch.objects.all():
        if branch.title != branch.code:
            branch.title = branch.code
            branch.save(update_fields=['title'])


def noop(apps, schema_editor):
    """The titles are derived data — nothing to restore on the way back."""


class Migration(migrations.Migration):

    dependencies = [
        ('app_records', '0006_alter_branch_title'),
    ]

    operations = [
        migrations.RunPython(title_from_code, noop),
    ]
