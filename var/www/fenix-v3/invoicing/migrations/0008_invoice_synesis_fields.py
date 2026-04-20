from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("invoicing", "0007_invoice_credit_note_for"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="source",
            field=models.CharField(blank=True, default="", max_length=20, verbose_name="Izvor"),
        ),
        migrations.AddField(
            model_name="invoice",
            name="synesis_id",
            field=models.CharField(blank=True, max_length=50, verbose_name="Synesis ID"),
        ),
        migrations.AddField(
            model_name="invoice",
            name="synesis_year",
            field=models.IntegerField(blank=True, null=True, verbose_name="Synesis godina"),
        ),
        migrations.AddField(
            model_name="invoice",
            name="synesis_hash",
            field=models.CharField(blank=True, max_length=64, verbose_name="Synesis hash"),
        ),
        migrations.AddField(
            model_name="invoice",
            name="is_locked",
            field=models.BooleanField(default=False, verbose_name="Zaključano"),
        ),
    ]
