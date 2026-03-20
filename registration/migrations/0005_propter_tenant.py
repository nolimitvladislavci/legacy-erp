# registration/migrations/0005_propter_tenant.py
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('companies', '0018_initial'),
        ('registration', '0004_add_promo_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='PropterTenant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('operator_name', models.CharField(blank=True, help_text='Npr. KS Limit d.o.o.', max_length=200, verbose_name='Operator / knjigovodstveni servis')),
                ('tier', models.CharField(choices=[('client', 'Direktni klijent (30-80 EUR/mj)'), ('bookkeeper', 'Knjigovodstveni servis (150-200 EUR/mj)')], default='client', max_length=20, verbose_name='Tip pretplate')),
                ('max_companies', models.PositiveIntegerField(default=1, help_text='Za bookkeepere: koliko klijenata mogu voditi', verbose_name='Max tvrtki')),
                ('fina_cert_status', models.CharField(choices=[('none', 'Nema certifikata'), ('pending', 'Zahtjev poslan'), ('active', 'Aktivan'), ('expiring', 'Istice uskoro'), ('expired', 'Istekao')], default='none', max_length=15, verbose_name='Status FINA certifikata')),
                ('modules_enabled', models.JSONField(default=list, help_text='Popis omogucenih Propter modula', verbose_name='Omoguceni moduli')),
                ('monthly_fee', models.DecimalField(decimal_places=2, default=0, max_digits=8, verbose_name='Mjesecna naknada (EUR)')),
                ('billing_day', models.PositiveIntegerField(default=1, verbose_name='Dan fakturiranja')),
                ('next_billing', models.DateField(blank=True, null=True, verbose_name='Sljedece fakturiranje')),
                ('eracuni_sent_total', models.PositiveIntegerField(default=0, verbose_name='Ukupno poslanih e-racuna')),
                ('eracuni_sent_month', models.PositiveIntegerField(default=0, verbose_name='e-Racuna ovaj mjesec')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktivan')),
                ('notes', models.TextField(blank=True, verbose_name='Napomene')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='propter_tenant', to='companies.company')),
                ('managed_by', models.ForeignKey(blank=True, help_text='Knjigovodstveni servis koji upravlja ovom tvrtkom', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='managed_tenants', to='registration.proptertenant', verbose_name='Upravljano od')),
            ],
            options={
                'verbose_name': 'Propter korisnik',
                'verbose_name_plural': 'Propter korisnici',
                'ordering': ['-created_at'],
            },
        ),
    ]
