"""
Migration 0035: Training mode, Partial payment support, Customer Display, POS Pulse.
- POSTerminal.is_training — obuka bez fiskalizacije
- POSReceipt.is_training — oznaka da je bon iz obuke
- POSReceipt.is_partial_paid — djelomično plaćanje flag
- POSSession.is_training — session-level training flag
- POSPulseEvent — AI živčani sustav, anomaly detection
- CustomerDisplayToken — token za pristup customer display
"""

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0034_add_access_token"),
        ("companies", "0001_initial"),
    ]

    operations = [
        # Training mode
        migrations.AddField(
            model_name="posterminal",
            name="is_training",
            field=models.BooleanField(
                default=False,
                verbose_name="Training modus",
                help_text="Bonovi se NE fiskaliziraju. Watermark OBUKA na svim bonovima.",
            ),
        ),
        migrations.AddField(
            model_name="possession",
            name="is_training",
            field=models.BooleanField(default=False, verbose_name="Training smjena"),
        ),
        migrations.AddField(
            model_name="posreceipt",
            name="is_training",
            field=models.BooleanField(
                default=False, verbose_name="Training bon", help_text="Bon iz obuke — nema fiskalnu vrijednost"
            ),
        ),
        # Customer display token
        migrations.AddField(
            model_name="posterminal",
            name="display_token",
            field=models.CharField(
                max_length=32,
                unique=True,
                blank=True,
                null=True,
                verbose_name="Customer Display token",
                help_text="Token za pristup ekranu kupca (drugi ekran/tablet).",
            ),
        ),
        # POS Pulse — AI živčani sustav
        migrations.CreateModel(
            name="POSPulseEvent",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="pulse_events", to="companies.company"
                    ),
                ),
                (
                    "terminal",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="pulse_events",
                        to="pos.posterminal",
                        null=True,
                        blank=True,
                    ),
                ),
                (
                    "event_type",
                    models.CharField(
                        max_length=30,
                        choices=[
                            ("anomaly_cancel", "Neobičan storno"),
                            ("anomaly_discount", "Neobičan popust"),
                            ("anomaly_cash", "Cash manjak"),
                            ("anomaly_void", "Masovni storno"),
                            ("anomaly_speed", "Prebrza naplata"),
                            ("anomaly_refund", "Sumnjivi povrat"),
                            ("heartbeat", "Terminal heartbeat"),
                            ("alert_stock", "Kritična zaliha"),
                            ("alert_fiscal", "Fiskalizacija fail"),
                            ("milestone_100", "100. bon danas"),
                            ("milestone_revenue", "Revenue milestone"),
                            ("shift_open", "Smjena otvorena"),
                            ("shift_close", "Smjena zatvorena"),
                        ],
                        verbose_name="Tip događaja",
                    ),
                ),
                (
                    "severity",
                    models.CharField(
                        max_length=10,
                        choices=[
                            ("info", "Info"),
                            ("warning", "Upozorenje"),
                            ("critical", "Kritično"),
                            ("success", "Uspjeh"),
                        ],
                        default="info",
                        verbose_name="Ozbiljnost",
                    ),
                ),
                ("title", models.CharField(max_length=200, verbose_name="Naslov")),
                ("detail", models.TextField(blank=True, verbose_name="Detalji")),
                ("metadata", models.JSONField(null=True, blank=True)),
                ("is_read", models.BooleanField(default=False)),
                ("notified_whatsapp", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "POS Pulse Event",
                "verbose_name_plural": "POS Pulse Events",
                "ordering": ["-created_at"],
            },
        ),
    ]
