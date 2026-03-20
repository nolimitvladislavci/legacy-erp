from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0027_posreceipt_fiscal_last_error_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='posreceiptitem',
            name='is_nonprofit_activity',
            field=models.BooleanField(
                default=False,
                help_text='Clanarina/donacija — ne fiskalizira se',
                verbose_name='Neprofitna djelatnost',
            ),
        ),
    ]
