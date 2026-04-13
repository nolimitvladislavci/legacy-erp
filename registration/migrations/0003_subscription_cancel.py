from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("registration", "0009_saleslead_ref_commission")]
    operations = [
        migrations.AddField(
            model_name="companysubscription",
            name="cancel_at_period_end",
            field=models.BooleanField(default=False, verbose_name="Otkaži na kraju perioda"),
        ),
        migrations.AddField(
            model_name="companysubscription",
            name="cancelled_at",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Datum otkazivanja"),
        ),
    ]
