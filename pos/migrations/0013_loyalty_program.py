from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('companies', '0001_initial'),
        ('pos', '0012_waiter_system'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoyaltyProgram',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Naziv')),
                ('program_type', models.CharField(choices=[('stamp', 'Stamp Card'), ('discount', 'Popust'), ('combo', 'Combo Deal')], default='stamp', max_length=10)),
                ('stamps_required', models.IntegerField(default=5, verbose_name='Potrebno pecata')),
                ('reward_description', models.CharField(blank=True, max_length=200, verbose_name='Opis nagrade')),
                ('applicable_category', models.CharField(blank=True, max_length=20, verbose_name='Kategorija')),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loyalty_programs', to='companies.company', verbose_name='Tvrtka')),
            ],
            options={'verbose_name': 'Program lojalnosti', 'verbose_name_plural': 'Programi lojalnosti'},
        ),
        migrations.CreateModel(
            name='GuestLoyalty',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('guest_email', models.EmailField(max_length=254, verbose_name='Email gosta')),
                ('guest_name', models.CharField(blank=True, max_length=100)),
                ('stamps', models.IntegerField(default=0, verbose_name='Pecati')),
                ('rewards_claimed', models.IntegerField(default=0, verbose_name='Nagrade iskoristene')),
                ('total_spent', models.DecimalField(decimal_places=2, default=0, max_digits=10)),
                ('last_visit', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='guest_loyalties', to='companies.company', verbose_name='Tvrtka')),
                ('program', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='pos.loyaltyprogram')),
            ],
            options={
                'verbose_name': 'Lojalnost gosta',
                'verbose_name_plural': 'Lojalnosti gostiju',
                'unique_together': {('company', 'program', 'guest_email')},
            },
        ),
    ]
