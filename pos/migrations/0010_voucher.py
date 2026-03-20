import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0001_initial'),
        ('pos', '0009_cancel_reason'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Voucher',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='Kod vaučera')),
                ('original_amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Izvorna vrijednost (€)')),
                ('remaining', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Preostalo (€)')),
                ('expiry_date', models.DateField(blank=True, null=True, verbose_name='Rok valjanosti')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktivan')),
                ('notes', models.CharField(blank=True, max_length=200, verbose_name='Napomena')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='vouchers', to='companies.company', verbose_name='Tvrtka')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='created_vouchers', to=settings.AUTH_USER_MODEL, verbose_name='Kreirao')),
            ],
            options={
                'verbose_name': 'Vaučer',
                'verbose_name_plural': 'Vaučeri',
                'ordering': ['-created_at'],
            },
        ),
    ]
