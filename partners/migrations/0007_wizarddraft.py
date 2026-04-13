from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("partners", "0006_add_buyer_type_invoice_routing"),
        ("companies", "0031_add_tc_consent_gdpr_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="WizardDraft",
            fields=[
                ("id", models.AutoField(primary_key=True)),
                # Tracking
                ("session_key", models.CharField(max_length=64, unique=True, db_index=True)),
                ("ip_address", models.GenericIPAddressField(null=True, blank=True)),
                ("user_agent", models.TextField(blank=True, default="")),
                # T&C (korak 0 — GDPR gatekeeper)
                ("tc_accepted", models.BooleanField(default=False)),
                ("tc_accepted_at", models.DateTimeField(null=True, blank=True)),
                # Korak 1 — djelatnosti
                ("nkd_codes_json", models.JSONField(default=list, blank=True)),
                # Korak 2 — ime firme
                ("firma_ime", models.CharField(max_length=200, blank=True, default="")),
                # Korak 3 — osnivači
                ("broj_osnivaca", models.PositiveSmallIntegerField(default=1)),
                ("direktor_ime", models.CharField(max_length=200, blank=True, default="")),
                ("direktor_oib", models.CharField(max_length=11, blank=True, default="")),
                ("direktor_email", models.EmailField(blank=True, default="")),
                # Korak 4 — kapital
                (
                    "kapital_tip",
                    models.CharField(max_length=10, default="jdoo", choices=[("jdoo", "j.d.o.o."), ("doo", "d.o.o.")]),
                ),
                # Korak 5 — sjedište
                ("koristi_konjik", models.BooleanField(default=True)),
                ("sjediste_adresa", models.CharField(max_length=200, blank=True, default="")),
                ("sjediste_grad", models.CharField(max_length=100, blank=True, default="")),
                ("sjediste_zip", models.CharField(max_length=20, blank=True, default="")),
                # Status funnel
                ("current_step", models.PositiveSmallIntegerField(default=0)),
                ("completed", models.BooleanField(default=False)),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                # Veza na kreiran Company (pending)
                (
                    "pending_company",
                    models.ForeignKey(
                        "companies.Company",
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wizard_drafts",
                    ),
                ),
                # Računovodstvena firma (Marija = booking agent)
                (
                    "accounting_firm",
                    models.ForeignKey(
                        "companies.Company",
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="wizard_managed_drafts",
                    ),
                ),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "partners_wizard_draft",
                "ordering": ["-updated_at"],
                "verbose_name": "Wizard Draft",
                "verbose_name_plural": "Wizard Drafts",
            },
        ),
    ]
