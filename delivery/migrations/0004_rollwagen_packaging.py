from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0003_coldchainzone_consolidateddelivery_sensorreading_and_more"),
        ("companies", "0013_grosmarkt_partner"),
    ]
    operations = [
        migrations.CreateModel(
            name="Rollwagen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("qr_code", models.CharField(max_length=100, unique=True, verbose_name="QR Kod")),
                (
                    "load_order",
                    models.PositiveIntegerField(
                        default=1,
                        verbose_name="Redoslijed utovara (LIFO)",
                        help_text="Veći broj = tovari se prvi (kraj kamiona), istovaruje se zadnji",
                    ),
                ),
                ("is_loaded", models.BooleanField(default=False, verbose_name="Ukrcano u kamion")),
                ("loaded_at", models.DateTimeField(null=True, blank=True)),
                ("notes", models.CharField(max_length=200, blank=True)),
                (
                    "consolidated_delivery",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="rollwagens",
                        to="delivery.consolidateddelivery",
                    ),
                ),
                (
                    "delivery_stop",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="rollwagens",
                        to="delivery.deliverystop",
                    ),
                ),
            ],
            options={
                "verbose_name": "Rollwagen",
                "verbose_name_plural": "Rollwagen",
                "ordering": ["-load_order"],
            },
        ),
        migrations.CreateModel(
            name="PackagingExchange",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "packaging_type",
                    models.CharField(
                        max_length=50,
                        verbose_name="Tip ambalaže",
                        choices=[
                            ("ifco", "IFCO Gajba"),
                            ("euro_pallet", "Europaleta"),
                            ("chep", "CHEP Paleta"),
                            ("crate_plastic", "Plastična gajba"),
                            ("crate_wood", "Drvena gajba"),
                            ("other", "Ostalo"),
                        ],
                    ),
                ),
                ("delivered_qty", models.PositiveIntegerField(default=0, verbose_name="Dostavljeno punih")),
                ("returned_qty", models.PositiveIntegerField(default=0, verbose_name="Vraćeno praznih")),
                ("balance", models.IntegerField(default=0, editable=False, verbose_name="Saldo (dug kupca)")),
                (
                    "photo",
                    models.ImageField(
                        upload_to="delivery/packaging/", blank=True, null=True, verbose_name="Foto dokaz"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "delivery_stop",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="packaging_exchanges",
                        to="delivery.deliverystop",
                    ),
                ),
            ],
            options={
                "verbose_name": "Razmjena ambalaže",
                "verbose_name_plural": "Razmjene ambalaže",
            },
        ),
    ]
