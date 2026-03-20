from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0008_warehouse_hub'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketplaceproduct',
            name='is_fragile',
            field=models.BooleanField(default=False, verbose_name='Krhko (ne trpi tezinu)'),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='is_heavy',
            field=models.BooleanField(default=False, verbose_name='Tesko (25+ kg)'),
        ),
    ]
