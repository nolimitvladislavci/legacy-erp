from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_pfand_linked_item"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="kalo_percent",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Prirodni kalo (npr. 2.5%)",
                max_digits=5,
                verbose_name="Kalo %",
            ),
        ),
    ]
