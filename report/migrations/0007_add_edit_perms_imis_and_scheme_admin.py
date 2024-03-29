# Generated by Django 3.2.18 on 2023-04-26 12:45
import logging

from django.db import migrations
from core.models import RoleRight, Role
from core.utils import insert_role_right_for_system

logger = logging.getLogger(__name__)

SCHEME_ADMIN_ROLE_IS_SYSTEM = 32
IMIS_ADMIN_ROLE_IS_SYSTEM = 64
EDIT_REPORT_ROLE_RIGHT_ID = 131225


def add_rights(apps, schema_editor):
    """
    Add edit_report permission to the IMIS Administrator and Scheme Administrator.
    """
    for ROLE_IS_SYSTEM in [SCHEME_ADMIN_ROLE_IS_SYSTEM, IMIS_ADMIN_ROLE_IS_SYSTEM]:
        insert_role_right_for_system(ROLE_IS_SYSTEM, EDIT_REPORT_ROLE_RIGHT_ID)


def remove_rights(apps, schema_editor):
    """
    Remove edit_report permission to the IMIS Administrator and Scheme Administrator.
    """
    role_is_system_values = [32, 64]
    RoleRight.objects.filter(
        role__is_system__in=role_is_system_values,
        right_id=EDIT_REPORT_ROLE_RIGHT_ID,
        validity_to__isnull=True
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('report', '0006_version_report_def'),
    ]

    operations = [
        migrations.RunPython(add_rights, remove_rights),
    ]
