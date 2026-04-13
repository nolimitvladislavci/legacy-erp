"""Data migration: update all EmployeeProfile.overtime_rate from 30% to 50% (ZOR čl.94 st.2)."""

from django.db import migrations
from decimal import Decimal


def fix_overtime_rates(apps, schema_editor):
    EmployeeProfile = apps.get_model("worktime", "EmployeeProfile")
    updated = EmployeeProfile.objects.filter(overtime_rate=Decimal("30.00")).update(overtime_rate=Decimal("50.00"))
    if updated:
        print(f"\n  Fixed {updated} employee profiles: overtime 30% → 50% (ZOR čl.94)")


class Migration(migrations.Migration):
    dependencies = [
        ("worktime", "0016_fix_overtime_zor_50pct"),
    ]

    operations = [
        migrations.RunPython(fix_overtime_rates, migrations.RunPython.noop),
    ]
