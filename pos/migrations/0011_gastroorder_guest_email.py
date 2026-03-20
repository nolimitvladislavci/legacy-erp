from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('pos', '0010_voucher'),
    ]

    operations = [
        migrations.AddField(
            model_name='gastroorder',
            name='guest_email',
            field=models.EmailField(blank=True, max_length=254, verbose_name='Email gosta'),
        ),
    ]
