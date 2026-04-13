from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0012_add_swift_bic"),
    ]
    operations = [
        migrations.AddField(
            model_name="company",
            name="grosmarkt_partner",
            field=models.BooleanField(
                default=False, verbose_name="Grosmarkt Partner", help_text="Prikazati na grosmarkt-online.eu?"
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="grosmarkt_role",
            field=models.CharField(
                max_length=30,
                blank=True,
                choices=[
                    ("logistik", "Logistik-Hub"),
                    ("gaertnerei", "Gärtnerei / Frischware"),
                    ("haendler", "Händler / Großhandel"),
                    ("gastro", "Gastronomie"),
                    ("sonstiges", "Sonstiges"),
                ],
                verbose_name="Grosmarkt Rolle",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="grosmarkt_description",
            field=models.TextField(
                blank=True,
                max_length=300,
                verbose_name="Grosmarkt Beschreibung (DE)",
                help_text="Kratki opis koji se prikazuje na grosmarkt-online.eu karticama",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="grosmarkt_show_name",
            field=models.BooleanField(
                default=False,
                verbose_name="Prikaži naziv firme javno",
                help_text="Ako False, prikazuje se samo rola (anonimizirano)",
            ),
        ),
        migrations.AlterField(
            model_name="company",
            name="oib",
            field=models.CharField(
                max_length=50,
                unique=True,
                verbose_name="OIB / Steuernummer",
            ),
        ),
    ]
