from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0021_extend_onboarding"),
    ]
    operations = [
        migrations.CreateModel(
            name="CompanyModuleConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True)),
                (
                    "company",
                    models.OneToOneField(
                        on_delete=models.CASCADE, to="companies.Company", related_name="module_config"
                    ),
                ),
                (
                    "enabled_modules",
                    models.JSONField(
                        default=list,
                        blank=True,
                        verbose_name="Aktivni moduli",
                        help_text="Lista ID-jeva aktivnih modula",
                    ),
                ),
                ("sidebar_order", models.JSONField(default=list, blank=True, verbose_name="Redoslijed u sidebaru")),
                ("ai_recommended", models.JSONField(default=list, blank=True, verbose_name="AI preporuceni moduli")),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Konfiguracija modula",
            },
        ),
    ]
