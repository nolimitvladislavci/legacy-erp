"""
Migracija kreirana ručno — tablice već postoje u bazi (kreirane SQL-om).
Django ih ne dira, samo bilježi stanje.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("companies", "__first__"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name="SeasonalWorker",
                    fields=[
                        ("id", models.AutoField(primary_key=True)),
                        (
                            "company",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="seasonal_workers",
                                to="companies.company",
                            ),
                        ),
                        ("first_name", models.CharField(max_length=100)),
                        ("last_name", models.CharField(max_length=100)),
                        ("oib", models.CharField(max_length=11)),
                        ("nationality", models.CharField(default="HR", max_length=10)),
                        ("date_of_birth", models.DateField(blank=True, null=True)),
                        ("address", models.CharField(blank=True, max_length=300)),
                        ("phone", models.CharField(blank=True, max_length=30)),
                        ("email", models.EmailField(blank=True)),
                        ("iban", models.CharField(blank=True, max_length=34)),
                        ("notes", models.TextField(blank=True)),
                        ("is_active", models.BooleanField(default=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                    ],
                    options={
                        "ordering": ["last_name", "first_name"],
                        "verbose_name": "Sezonski radnik",
                        "verbose_name_plural": "Sezonski radnici",
                    },
                ),
                migrations.CreateModel(
                    name="SeasonalContract",
                    fields=[
                        ("id", models.AutoField(primary_key=True)),
                        (
                            "worker",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="contracts",
                                to="seasonal.seasonalworker",
                            ),
                        ),
                        (
                            "company",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="seasonal_contracts",
                                to="companies.company",
                            ),
                        ),
                        ("contract_type", models.CharField(max_length=20)),
                        ("status", models.CharField(default="pending", max_length=15)),
                        ("start_date", models.DateField()),
                        ("end_date", models.DateField()),
                        ("gross_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                        ("payment_cycle", models.CharField(default="lump_sum", max_length=15)),
                        ("position", models.CharField(blank=True, max_length=200)),
                        ("hzmo_prijava_sent", models.BooleanField(default=False)),
                        ("hzmo_prijava_date", models.DateField(blank=True, null=True)),
                        ("hzmo_odjava_sent", models.BooleanField(default=False)),
                        ("hzmo_odjava_date", models.DateField(blank=True, null=True)),
                        ("contract_pdf", models.FileField(blank=True, null=True, upload_to="seasonal/contracts/")),
                        ("signed_at", models.DateTimeField(blank=True, null=True)),
                        ("notes", models.TextField(blank=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "created_by",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="auth.user",
                            ),
                        ),
                    ],
                    options={
                        "ordering": ["-start_date"],
                        "verbose_name": "Sezonski ugovor",
                        "verbose_name_plural": "Sezonski ugovori",
                    },
                ),
                migrations.CreateModel(
                    name="SeasonalPayment",
                    fields=[
                        ("id", models.AutoField(primary_key=True)),
                        (
                            "contract",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="payments",
                                to="seasonal.seasonalcontract",
                            ),
                        ),
                        (
                            "company",
                            models.ForeignKey(
                                on_delete=django.db.models.deletion.CASCADE,
                                related_name="seasonal_payments",
                                to="companies.company",
                            ),
                        ),
                        ("payment_date", models.DateField()),
                        ("gross_amount", models.DecimalField(decimal_places=2, max_digits=10)),
                        ("tax_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                        ("net_amount", models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                        ("payment_method", models.CharField(default="bank", max_length=10)),
                        ("status", models.CharField(default="planned", max_length=15)),
                        ("joppd_generated", models.BooleanField(default=False)),
                        ("joppd_date", models.DateField(blank=True, null=True)),
                        ("joppd_xml", models.TextField(blank=True)),
                        ("reference", models.CharField(blank=True, max_length=100)),
                        ("notes", models.TextField(blank=True)),
                        ("created_at", models.DateTimeField(auto_now_add=True)),
                        (
                            "approved_by",
                            models.ForeignKey(
                                blank=True,
                                null=True,
                                on_delete=django.db.models.deletion.SET_NULL,
                                related_name="+",
                                to="auth.user",
                            ),
                        ),
                    ],
                    options={
                        "ordering": ["-payment_date"],
                        "verbose_name": "Isplata sezonce",
                        "verbose_name_plural": "Isplate sezonskim radnicima",
                    },
                ),
            ],
            database_operations=[],  # Tablice već postoje
        ),
    ]
