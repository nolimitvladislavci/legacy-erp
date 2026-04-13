from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0014_inventura_models"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="is_nonprofit_activity",
            field=models.BooleanField(
                default=False,
                help_text="Clanarina, donacija, dotacija — NE fiskalizira se, NE pdv",
                verbose_name="Neprofitna djelatnost",
            ),
        ),
    ]
