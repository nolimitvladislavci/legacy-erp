from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0020_w1d_wholesale_min_qty_purchase_date"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="reserved_inhouse",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Količina rezervirana za gastro/konobu — ne ide na marketplace",
                max_digits=10,
                verbose_name="Rezervirano in-house",
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="reserved_marketplace",
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                help_text="Količina na aktivnim marketplace listinzima",
                max_digits=10,
                verbose_name="Rezervirano marketplace",
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="allocation_buffer_pct",
            field=models.PositiveIntegerField(
                default=10, help_text="Postotak zalihe koji se drži kao sigurnosni buffer", verbose_name="Buffer (%)"
            ),
        ),
    ]
