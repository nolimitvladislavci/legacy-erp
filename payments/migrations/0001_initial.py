import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PaymentConfig',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('stripe_enabled', models.BooleanField(default=False, verbose_name='Stripe aktivan')),
                ('stripe_public_key', models.CharField(blank=True, max_length=200, verbose_name='Stripe Publishable Key')),
                ('stripe_secret_key', models.CharField(blank=True, max_length=200, verbose_name='Stripe Secret Key')),
                ('stripe_webhook_secret', models.CharField(blank=True, max_length=200, verbose_name='Stripe Webhook Secret')),
                ('btcpay_enabled', models.BooleanField(default=False, verbose_name='BTCPay aktivan')),
                ('btcpay_url', models.URLField(blank=True, verbose_name='BTCPay Server URL')),
                ('btcpay_store_id', models.CharField(blank=True, max_length=100, verbose_name='BTCPay Store ID')),
                ('btcpay_api_key', models.CharField(blank=True, max_length=200, verbose_name='BTCPay API Key')),
                ('default_currency', models.CharField(default='EUR', max_length=3, verbose_name='Valuta')),
                ('auto_capture', models.BooleanField(default=True, verbose_name='Automatski naplati')),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payment_config', to='companies.company', verbose_name='Tvrtka')),
            ],
            options={'verbose_name': 'Konfiguracija placanja', 'verbose_name_plural': 'Konfiguracije placanja'},
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('source', models.CharField(choices=[('gastro_qr', 'Gastro QR Narudzba'), ('pos', 'POS Blagajna'), ('webshop', 'Webshop'), ('invoice', 'Faktura'), ('rental', 'Najam / Hostel'), ('booking', 'Rezervacija')], max_length=20, verbose_name='Izvor')),
                ('source_id', models.CharField(blank=True, max_length=100, verbose_name='ID izvora')),
                ('method', models.CharField(choices=[('cash', 'Gotovina'), ('stripe', 'Kartica (Stripe)'), ('btcpay', 'Kriptovaluta (BTCPay)')], max_length=10, verbose_name='Nacin placanja')),
                ('status', models.CharField(choices=[('pending', 'Na cekanju'), ('processing', 'U obradi'), ('completed', 'Zavrseno'), ('failed', 'Neuspjesno'), ('refunded', 'Povrat'), ('cancelled', 'Otkazano')], default='pending', max_length=15, verbose_name='Status')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Iznos')),
                ('currency', models.CharField(default='EUR', max_length=3)),
                ('description', models.CharField(blank=True, max_length=300, verbose_name='Opis')),
                ('external_id', models.CharField(blank=True, max_length=300, verbose_name='Vanjski ID')),
                ('external_url', models.URLField(blank=True, verbose_name='Vanjski URL')),
                ('gateway_data', models.JSONField(blank=True, default=dict, verbose_name='Gateway podaci')),
                ('customer_email', models.EmailField(blank=True, max_length=254, verbose_name='Email kupca')),
                ('customer_name', models.CharField(blank=True, max_length=100, verbose_name='Ime kupca')),
                ('crypto_currency', models.CharField(blank=True, max_length=10, verbose_name='Kripto valuta')),
                ('crypto_amount', models.CharField(blank=True, max_length=30, verbose_name='Kripto iznos')),
                ('crypto_address', models.CharField(blank=True, max_length=200, verbose_name='Crypto adresa')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='companies.company', verbose_name='Tvrtka')),
            ],
            options={
                'verbose_name': 'Placanje',
                'verbose_name_plural': 'Placanja',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['company', 'status'], name='payments_pa_company_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['source', 'source_id'], name='payments_pa_source_idx'),
        ),
        migrations.AddIndex(
            model_name='payment',
            index=models.Index(fields=['external_id'], name='payments_pa_extern_idx'),
        ),
    ]
