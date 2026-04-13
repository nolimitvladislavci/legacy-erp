from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("companies", "0016_company_no_show_tolerance_minutes"),
    ]

    operations = [
        migrations.AddField(
            model_name="company",
            name="allow_negative_stock",
            field=models.BooleanField(
                default=True,
                verbose_name="Dozvoli negativne zalihe",
                help_text="Ako je uključeno, prodaja je moguća i kad je stanje 0.",
            ),
        ),
    ]
