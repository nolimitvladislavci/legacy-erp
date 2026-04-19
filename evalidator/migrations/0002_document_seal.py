from django.db import migrations, models
import evalidator.models


class Migration(migrations.Migration):
    dependencies = [
        ("evalidator", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentSeal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "seal_token",
                    models.CharField(
                        default=evalidator.models._gen_seal_token,
                        db_index=True,
                        help_text="8-char kod (URL-safe). Embed u QR i PDF footer.",
                        max_length=8,
                        unique=True,
                    ),
                ),
                (
                    "sha256_hash",
                    models.CharField(
                        db_index=True, help_text="SHA-256 hex digest sadržaja datoteke pri pečaćenju.", max_length=64
                    ),
                ),
                ("arhiva_entry_id", models.PositiveIntegerField(blank=True, db_index=True, null=True)),
                ("arhiva_company_id", models.PositiveIntegerField(blank=True, null=True)),
                ("doc_number", models.CharField(blank=True, max_length=255)),
                ("doc_date", models.DateField(blank=True, null=True)),
                ("partner_name", models.CharField(blank=True, max_length=200)),
                ("amount", models.DecimalField(blank=True, decimal_places=2, max_digits=14, null=True)),
                ("currency", models.CharField(blank=True, default="EUR", max_length=3)),
                ("issuer_name", models.CharField(blank=True, help_text="Naziv firme koja je pečatila", max_length=200)),
                ("issuer_country", models.CharField(blank=True, default="HR", max_length=2)),
                ("sealed_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("sealed_by_user_id", models.PositiveIntegerField(blank=True, null=True)),
                ("sealed_by_username", models.CharField(blank=True, max_length=150)),
                (
                    "expires_at",
                    models.DateTimeField(
                        blank=True, help_text="Null = trajno. Inače: datum isteka (npr. 10 godina GoBD).", null=True
                    ),
                ),
                (
                    "send_channel",
                    models.CharField(blank=True, help_text="email, whatsapp, portal, datev", max_length=50),
                ),
                (
                    "viral_code",
                    models.CharField(
                        blank=True, db_index=True, help_text="Viralni kod za onboarding landing page", max_length=12
                    ),
                ),
                (
                    "verify_count",
                    models.PositiveIntegerField(default=0, help_text="Koliko puta je verifikacijska stranica otvorena"),
                ),
                ("last_verified_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "db_table": "evalidator_document_seal",
                "ordering": ["-sealed_at"],
                "indexes": [
                    models.Index(fields=["sha256_hash"], name="ev_seal_hash_idx"),
                    models.Index(fields=["viral_code"], name="ev_seal_viral_idx"),
                    models.Index(fields=["arhiva_entry_id"], name="ev_seal_entry_idx"),
                ],
            },
        ),
    ]
