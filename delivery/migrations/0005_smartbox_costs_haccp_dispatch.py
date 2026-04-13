from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0004_rollwagen_packaging"),
        ("companies", "0013_grosmarkt_partner"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        # SmartBox — termo kutija sa senzorom i GPS-om
        migrations.CreateModel(
            name="SmartBox",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("box_id", models.CharField(max_length=50, unique=True, verbose_name="Oznaka kutije")),
                (
                    "box_type",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("styrofoam", "Styropor (lokalna dostava)"),
                            ("insulated", "Izolirana kutija (srednja)"),
                            ("active_cool", "Aktivno hlađena (senzor+GPS)"),
                        ],
                        default="styrofoam",
                    ),
                ),
                ("has_sensor", models.BooleanField(default=False, verbose_name="Ima temperaturni senzor")),
                ("has_gps", models.BooleanField(default=False, verbose_name="Ima GPS tracker")),
                ("sensor_device_id", models.CharField(max_length=100, blank=True, verbose_name="ID senzora/GPS-a")),
                ("qr_code", models.CharField(max_length=100, unique=True, verbose_name="QR kod")),
                (
                    "target_min_temp",
                    models.DecimalField(
                        max_digits=5, decimal_places=1, default=Decimal("2.0"), verbose_name="Min temp (°C)"
                    ),
                ),
                (
                    "target_max_temp",
                    models.DecimalField(
                        max_digits=5, decimal_places=1, default=Decimal("8.0"), verbose_name="Max temp (°C)"
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("available", "Dostupna"),
                            ("in_use", "U upotrebi"),
                            ("returning", "Vraća se"),
                            ("maintenance", "Na servisu"),
                        ],
                        default="available",
                    ),
                ),
                (
                    "current_delivery",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="smart_boxes",
                        to="delivery.consolidateddelivery",
                    ),
                ),
                (
                    "current_stop",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="smart_boxes",
                        to="delivery.deliverystop",
                    ),
                ),
                (
                    "owner_company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="smart_boxes", to="companies.company"
                    ),
                ),
                ("last_lat", models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)),
                ("last_lng", models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)),
                ("last_temp", models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)),
                ("last_reading_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Smart Box",
                "verbose_name_plural": "Smart Boxes",
                "ordering": ["box_id"],
            },
        ),
        # DeliveryCostRule — cijena po km za svaku metodu
        migrations.CreateModel(
            name="DeliveryCostRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "region",
                    models.CharField(
                        max_length=30,
                        choices=[
                            ("osijek_local", "Osijek lokalno (<15km)"),
                            ("slavonija", "Slavonija (15-80km)"),
                            ("dalmatia", "Dalmacija (80-400km)"),
                            ("stuttgart_local", "Stuttgart lokalno (<20km)"),
                            ("bw_region", "Baden-Württemberg (20-100km)"),
                        ],
                        verbose_name="Regija",
                    ),
                ),
                (
                    "delivery_method",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("internal", "Vlastita dostava"),
                            ("taxi", "Taxi dostava"),
                            ("crowd", "Crowd-shipping (Gepek)"),
                            ("bus", "Autobusna linija"),
                            ("courier", "Kurirska služba"),
                        ],
                        verbose_name="Metoda dostave",
                    ),
                ),
                (
                    "base_fee",
                    models.DecimalField(
                        max_digits=8, decimal_places=2, default=Decimal("2.00"), verbose_name="Osnovna cijena (€)"
                    ),
                ),
                (
                    "per_km_fee",
                    models.DecimalField(
                        max_digits=6, decimal_places=2, default=Decimal("0.50"), verbose_name="Cijena po km (€)"
                    ),
                ),
                (
                    "min_order_value",
                    models.DecimalField(
                        max_digits=8,
                        decimal_places=2,
                        default=Decimal("15.00"),
                        verbose_name="Min vrijednost narudžbe (€)",
                    ),
                ),
                ("max_distance_km", models.PositiveIntegerField(default=50, verbose_name="Max udaljenost (km)")),
                (
                    "cold_chain_surcharge",
                    models.DecimalField(
                        max_digits=6,
                        decimal_places=2,
                        default=Decimal("1.50"),
                        verbose_name="Dodatak za hladni lanac (€)",
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                (
                    "hub_company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="delivery_cost_rules",
                        to="companies.company",
                    ),
                ),
            ],
            options={
                "verbose_name": "Pravilo cijene dostave",
                "verbose_name_plural": "Pravila cijena dostave",
                "unique_together": [("hub_company", "region", "delivery_method")],
            },
        ),
        # TransportHandoff — HACCP primopredajni zapis
        migrations.CreateModel(
            name="TransportHandoff",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "handoff_type",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("hub_to_driver", "Hub → Vozač"),
                            ("driver_to_customer", "Vozač → Kupac"),
                            ("customer_return", "Kupac → Povrat kutije"),
                        ],
                        verbose_name="Tip primopredaje",
                    ),
                ),
                (
                    "delivery_stop",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="handoffs",
                        to="delivery.deliverystop",
                    ),
                ),
                (
                    "smart_box",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="handoffs",
                        to="delivery.smartbox",
                    ),
                ),
                (
                    "consolidated_delivery",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="handoffs",
                        to="delivery.consolidateddelivery",
                    ),
                ),
                (
                    "performed_by",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        related_name="delivery_handoffs",
                    ),
                ),
                (
                    "temperature_at_handoff",
                    models.DecimalField(
                        max_digits=5, decimal_places=1, null=True, blank=True, verbose_name="Temp pri primopredaji (°C)"
                    ),
                ),
                ("photo", models.ImageField(upload_to="delivery/handoffs/", blank=True, null=True)),
                ("recipient_name", models.CharField(max_length=100, blank=True)),
                ("haccp_checklist", models.JSONField(default=dict, blank=True, verbose_name="HACCP kontrolna lista")),
                ("notes", models.TextField(blank=True)),
                ("latitude", models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)),
                ("longitude", models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Primopredajni zapis",
                "verbose_name_plural": "Primopredajni zapisi",
                "ordering": ["-created_at"],
            },
        ),
        # DispatchOffer — ponuda taksistima/gepek vozačima
        migrations.CreateModel(
            name="DispatchOffer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "consolidated_delivery",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="dispatch_offers",
                        to="delivery.consolidateddelivery",
                    ),
                ),
                (
                    "driver",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        related_name="dispatch_offers",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        max_length=20,
                        choices=[
                            ("pending", "Ponuđeno"),
                            ("accepted", "Prihvaćeno"),
                            ("rejected", "Odbijeno"),
                            ("expired", "Isteklo"),
                            ("completed", "Završeno"),
                        ],
                        default="pending",
                    ),
                ),
                (
                    "offered_price",
                    models.DecimalField(max_digits=8, decimal_places=2, verbose_name="Ponuđena cijena (€)"),
                ),
                (
                    "driver_earnings",
                    models.DecimalField(
                        max_digits=8, decimal_places=2, default=Decimal("0"), verbose_name="Zarada vozača (€)"
                    ),
                ),
                (
                    "estimated_km",
                    models.DecimalField(
                        max_digits=6, decimal_places=1, default=Decimal("0"), verbose_name="Procjena km"
                    ),
                ),
                ("estimated_stops", models.PositiveIntegerField(default=1)),
                ("pickup_address", models.CharField(max_length=300, blank=True)),
                ("requires_cold_chain", models.BooleanField(default=False)),
                ("expires_at", models.DateTimeField(null=True, blank=True)),
                ("accepted_at", models.DateTimeField(null=True, blank=True)),
                ("completed_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "Dispatch ponuda",
                "verbose_name_plural": "Dispatch ponude",
                "ordering": ["-created_at"],
            },
        ),
    ]
