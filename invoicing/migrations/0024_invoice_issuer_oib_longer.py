from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0023_invoiceprofile_bilingual"),
    ]

    operations = [
        migrations.AlterField(
            model_name="invoice",
            name="issuer_oib",
            field=models.CharField(blank=True, max_length=30),
        ),
    ]
