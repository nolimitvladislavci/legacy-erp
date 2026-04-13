from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0017_add_swift_bic"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoiceitem",
            name="description",
            field=models.CharField(max_length=500, verbose_name="Opis stavke"),
        ),
    ]
