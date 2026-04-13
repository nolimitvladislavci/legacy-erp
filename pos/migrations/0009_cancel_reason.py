from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0008_dsfinvk_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="posreceipt",
            name="cancel_reason",
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name="Razlog storniranja",
            ),
        ),
    ]
