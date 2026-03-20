from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoicing', '0019_alter_invoiceitem_description'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='cancel_reason',
            field=models.CharField(
                blank=True,
                max_length=200,
                verbose_name='Razlog storniranja',
            ),
        ),
    ]
