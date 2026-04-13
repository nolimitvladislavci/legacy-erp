from django.db import migrations, models
import django.db.models.deletion
from decimal import Decimal


class Migration(migrations.Migration):
    dependencies = [
        ("delivery", "0005_smartbox_costs_haccp_dispatch"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        # SensorReading -> SmartBox FK
        migrations.AddField(
            model_name="sensorreading",
            name="smart_box",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sensor_readings",
                to="delivery.smartbox",
            ),
        ),
        # SmartBox HACCP status
        migrations.AddField(
            model_name="smartbox",
            name="haccp_status",
            field=models.CharField(
                max_length=20,
                choices=[
                    ("ok", "OK"),
                    ("warning", "Upozorenje"),
                    ("critical", "CRITICAL — lanac prekinut"),
                    ("blocked", "BLOKIRAN — ceka dispatchera"),
                ],
                default="ok",
            ),
        ),
        migrations.AddField(
            model_name="smartbox",
            name="haccp_blocked_at",
            field=models.DateTimeField(null=True, blank=True),
        ),
        # HACCPIncident model
        migrations.CreateModel(
            name="HACCPIncident",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "incident_type",
                    models.CharField(
                        max_length=30,
                        choices=[
                            ("sustained_breach", "Sustained Breach (>10min)"),
                            ("critical_failure", "Critical Failure (>15C)"),
                            ("offline_retroactive", "Offline Retroactive Detection"),
                        ],
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        max_length=10,
                        choices=[
                            ("warning", "Warning"),
                            ("critical", "Critical"),
                            ("blocked", "Blocked"),
                        ],
                        default="critical",
                    ),
                ),
                (
                    "smart_box",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="haccp_incidents",
                        to="delivery.smartbox",
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "consolidated_delivery",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="haccp_incidents",
                        to="delivery.consolidateddelivery",
                        null=True,
                        blank=True,
                    ),
                ),
                ("breach_start", models.DateTimeField(verbose_name="Pocetak prekrsaja")),
                ("breach_end", models.DateTimeField(null=True, blank=True, verbose_name="Kraj prekrsaja")),
                ("max_temperature", models.DecimalField(max_digits=5, decimal_places=1, verbose_name="Max temp (C)")),
                ("duration_minutes", models.IntegerField(default=0, verbose_name="Trajanje prekrsaja (min)")),
                ("description", models.TextField(blank=True)),
                ("is_resolved", models.BooleanField(default=False)),
                (
                    "resolved_by",
                    models.ForeignKey(
                        null=True,
                        blank=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="auth.user",
                        related_name="resolved_haccp_incidents",
                    ),
                ),
                ("resolution_note", models.TextField(blank=True, verbose_name="Sto je poduzeto")),
                ("resolved_at", models.DateTimeField(null=True, blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reading_ids", models.JSONField(default=list, blank=True, verbose_name="ID-jevi ocitanja")),
            ],
            options={
                "verbose_name": "HACCP Incident",
                "verbose_name_plural": "HACCP Incidents",
                "ordering": ["-created_at"],
            },
        ),
    ]
