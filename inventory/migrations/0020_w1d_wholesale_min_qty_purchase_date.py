from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0019_w1a_item_class_fiscal_treatment_asset"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryitem",
            name="wholesale_min_qty",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=2,
                default=1,
                verbose_name="Min. kol. za veleprodajnu cijenu",
                help_text="Ispod ove količine primjenjuje se maloprodajna cijena",
            ),
        ),
        migrations.AddField(
            model_name="inventoryitem",
            name="purchase_date",
            field=models.DateField(
                null=True, blank=True, verbose_name="Datum nabave", help_text="Za amortizacijsku kalkulaciju (assets)"
            ),
        ),
    ]
