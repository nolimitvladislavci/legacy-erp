from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("companies", "0004_business_profiles"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ImpersonationLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("started_at", models.DateTimeField(auto_now_add=True, verbose_name="Početak")),
                ("ended_at", models.DateTimeField(blank=True, null=True, verbose_name="Kraj")),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True, verbose_name="IP adresa")),
                ("actions_count", models.IntegerField(default=0, verbose_name="Broj akcija")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impersonation_logs",
                        to="companies.company",
                        verbose_name="Tvrtka",
                    ),
                ),
                (
                    "superadmin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="impersonation_sessions",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Superadmin",
                    ),
                ),
            ],
            options={
                "verbose_name": "Log impersonacije",
                "verbose_name_plural": "Logovi impersonacija",
                "ordering": ["-started_at"],
            },
        ),
    ]
