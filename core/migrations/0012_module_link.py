"""
0012_module_link.py — ModuleLink registar za fina-connect

Globalni registar svih modula/servisa na IP adresi 37.27.248.86.
Pretraživ imenom, opisom, ključnim riječima.
Svaki modul ima ikonu + link — jedini globalni ulaz podataka.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0011_genetic_search_blind_spots"),
    ]

    operations = [
        migrations.CreateModel(
            name="ModuleLink",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("icon",         models.CharField(max_length=10,  verbose_name="Ikona (emoji)")),
                ("name",         models.CharField(max_length=100, verbose_name="Puno ime")),
                ("name_short",   models.CharField(max_length=30,  verbose_name="Kratko ime")),
                ("description",  models.CharField(max_length=250, blank=True, verbose_name="Opis")),
                ("url",          models.CharField(max_length=300, verbose_name="URL (relativan)")),
                ("category",     models.CharField(max_length=20, default="other", choices=[
                    ("finance","Financije"), ("documents","Dokumenti"), ("hr","Zaposlenici / HR"),
                    ("crm","Komitenti / CRM"), ("pos","POS / Blagajna"),
                    ("specialty","Specijalizirani modul"), ("ai","AI / Inteligencija"),
                    ("security","Sigurnost"), ("settings","Postavke"), ("portal","Portal"),
                    ("animals","Životinje"), ("real_estate","Nekretnine / Gradnja"),
                    ("social","Socijala / Udruge"), ("other","Ostalo"),
                ])),
                ("roles",         models.JSONField(default=list, blank=True)),
                ("project",       models.CharField(max_length=20, default="fina-connect", choices=[
                    ("fenix-v3","Fenix V3"), ("fina-connect","Stari ERP"), ("shared","Zajednički"),
                ])),
                ("sort_order",    models.PositiveSmallIntegerField(default=0)),
                ("is_active",     models.BooleanField(default=True)),
                ("is_admin_only", models.BooleanField(default=False)),
                ("keywords",      models.CharField(max_length=400, blank=True)),
                ("created_at",    models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name":        "Modul / servis",
                "verbose_name_plural": "Moduli i servisi",
                "ordering":            ["sort_order", "category", "name"],
                "app_label":           "core",
            },
        ),
        migrations.AddIndex(
            model_name="modulelink",
            index=models.Index(fields=["project", "is_active"], name="core_ml_proj_idx"),
        ),
        migrations.AddIndex(
            model_name="modulelink",
            index=models.Index(fields=["category"], name="core_ml_cat_idx"),
        ),
    ]
