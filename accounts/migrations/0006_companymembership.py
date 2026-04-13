from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0001_initial"),
        ("accounts", "0005_userprofile_must_change_password"),
    ]

    operations = [
        migrations.CreateModel(
            name="CompanyMembership",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("superadmin", "Super Administrator"),
                            ("company_admin", "Admin tvrtke"),
                            ("project_manager", "Voditelj projekta"),
                            ("worker", "Radnik"),
                            ("investor", "Investitor"),
                            ("partner", "Partner / Klijent"),
                        ],
                        default="worker",
                        max_length=30,
                    ),
                ),
                ("is_default", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="memberships", to="companies.company"
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="company_memberships",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "accounts_companymembership",
                "verbose_name": "Membership",
                "verbose_name_plural": "Memberships",
                "unique_together": {("user", "company")},
            },
        ),
    ]
