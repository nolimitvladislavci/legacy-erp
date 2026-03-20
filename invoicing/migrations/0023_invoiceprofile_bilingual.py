from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0022_dunning_rule'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoiceprofile',
            name='bilingual',
            field=models.BooleanField(default=False, verbose_name='Dvojezični račun'),
        ),
        migrations.AddField(
            model_name='invoiceprofile',
            name='secondary_language',
            field=models.CharField(
                blank=True, default='', max_length=5,
                choices=[('hr', 'Hrvatski'), ('de', 'Deutsch'), ('en', 'English')],
                verbose_name='Drugi jezik',
            ),
        ),
    ]
