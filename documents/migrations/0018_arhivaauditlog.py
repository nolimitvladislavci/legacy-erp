from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0001_initial"),
        ("documents", "0017_arhivaentry_partner_arhivalabel_arhivaentry_labels"),
    ]

    operations = [
        migrations.CreateModel(
            name="ArhivaAuditLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("entry_archive_number", models.CharField(blank=True, max_length=50)),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("created", "Kreiran"),
                            ("updated", "Ažuriran"),
                            ("deleted", "Obrisan"),
                            ("viewed", "Pregledan"),
                            ("downloaded", "Preuzet"),
                            ("exported", "Eksportiran"),
                            ("ai_proposal", "AI prijedlog"),
                            ("booked", "Proknjižen"),
                            ("label_changed", "Oznaka promijenjena"),
                        ],
                        max_length=20,
                    ),
                ),
                ("ip_address", models.GenericIPAddressField(null=True)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("changes", models.JSONField(blank=True, default=dict)),
                ("timestamp", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="companies.company",
                    ),
                ),
                (
                    "entry",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="audit_logs",
                        to="documents.arhivaentry",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Arhiva Audit Log",
                "verbose_name_plural": "Arhiva Audit Logovi",
                "ordering": ["-timestamp"],
                "indexes": [
                    models.Index(fields=["company", "timestamp"], name="documents_a_company_audit_ts_idx"),
                    models.Index(fields=["entry", "timestamp"], name="documents_a_entry_audit_ts_idx"),
                ],
            },
        ),
    ]
