"""
ArhivaEntry photo registry extension.

Adds GPS, source tracking, photo metadata, and content classification
to support global photo gallery across all apps.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0021_add_ai_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # GPS / Location
        migrations.AddField(
            model_name="arhivaentry",
            name="latitude",
            field=models.FloatField(blank=True, null=True, verbose_name="GPS lat"),
        ),
        migrations.AddField(
            model_name="arhivaentry",
            name="longitude",
            field=models.FloatField(blank=True, null=True, verbose_name="GPS lng"),
        ),
        migrations.AddField(
            model_name="arhivaentry",
            name="address",
            field=models.CharField(blank=True, default="", max_length=500, verbose_name="Adresa"),
        ),
        # Cross-app source tracking
        migrations.AddField(
            model_name="arhivaentry",
            name="source_app",
            field=models.CharField(
                blank=True, db_index=True, default="", max_length=50, verbose_name="Izvorna aplikacija"
            ),
        ),
        migrations.AddField(
            model_name="arhivaentry",
            name="source_model",
            field=models.CharField(blank=True, default="", max_length=100, verbose_name="Izvorni model"),
        ),
        migrations.AddField(
            model_name="arhivaentry",
            name="source_object_id",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="ID izvornog objekta (FK)"),
        ),
        # Photo metadata
        migrations.AddField(
            model_name="arhivaentry",
            name="tags",
            field=models.JSONField(blank=True, default=list, verbose_name="Oznake"),
        ),
        migrations.AddField(
            model_name="arhivaentry",
            name="thumbnail_path",
            field=models.CharField(blank=True, default="", max_length=500, verbose_name="Putanja thumbnila"),
        ),
        migrations.AddField(
            model_name="arhivaentry",
            name="captured_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Vrijeme snimanja"),
        ),
        migrations.AddField(
            model_name="arhivaentry",
            name="captured_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="captured_photos",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Snimio",
            ),
        ),
        # Content classification
        migrations.AddField(
            model_name="arhivaentry",
            name="content_category",
            field=models.CharField(
                blank=True,
                default="document",
                max_length=30,
                choices=[
                    ("document", "Dokument"),
                    ("photo", "Fotografija"),
                    ("scan", "Sken"),
                    ("signature", "Potpis"),
                    ("certificate", "Certifikat"),
                    ("receipt", "Racun"),
                ],
                verbose_name="Kategorija sadrzaja",
            ),
        ),
        # Index for photo gallery queries
        migrations.AddIndex(
            model_name="arhivaentry",
            index=models.Index(
                fields=["company", "content_category", "-archived_at"],
                name="arhiva_photo_gallery_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="arhivaentry",
            index=models.Index(
                fields=["company", "source_app", "-archived_at"],
                name="arhiva_source_app_idx",
            ),
        ),
    ]
