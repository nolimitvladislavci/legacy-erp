from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='paymentconfig',
            name='paypal_enabled',
            field=models.BooleanField(default=False, verbose_name='PayPal aktivan'),
        ),
        migrations.AddField(
            model_name='paymentconfig',
            name='paypal_client_id',
            field=models.CharField(blank=True, max_length=200, verbose_name='PayPal Client ID'),
        ),
        migrations.AddField(
            model_name='paymentconfig',
            name='paypal_secret',
            field=models.CharField(blank=True, max_length=200, verbose_name='PayPal Secret'),
        ),
        migrations.AddField(
            model_name='paymentconfig',
            name='paypal_mode',
            field=models.CharField(choices=[('sandbox', 'Sandbox'), ('live', 'Live')], default='live', max_length=10, verbose_name='PayPal Mode'),
        ),
        migrations.AlterField(
            model_name='payment',
            name='method',
            field=models.CharField(choices=[('cash', 'Gotovina'), ('stripe', 'Kartica (Stripe)'), ('btcpay', 'Kriptovaluta (BTCPay)'), ('paypal', 'PayPal')], max_length=10, verbose_name='Nacin placanja'),
        ),
    ]
