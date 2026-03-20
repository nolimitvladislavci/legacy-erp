from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('companies', '0001_initial'),
        ('pos', '0011_gastroorder_guest_email'),
    ]

    operations = [
        migrations.AddField(
            model_name='gastroorder',
            name='claimed_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='claimed_orders', to=settings.AUTH_USER_MODEL, verbose_name='Preuzeo konobar'),
        ),
        migrations.AddField(
            model_name='gastroorder',
            name='claimed_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Vrijeme preuzimanja'),
        ),
        migrations.AddField(
            model_name='gastroorder',
            name='delivered_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='delivered_orders', to=settings.AUTH_USER_MODEL, verbose_name='Dostavio konobar'),
        ),
        migrations.AddField(
            model_name='gastroorder',
            name='delivered_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Vrijeme dostave'),
        ),
        migrations.CreateModel(
            name='WaiterShift',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('started_at', models.DateTimeField(auto_now_add=True, verbose_name='Pocetak smjene')),
                ('ended_at', models.DateTimeField(blank=True, null=True, verbose_name='Kraj smjene')),
                ('last_heartbeat', models.DateTimeField(auto_now_add=True, verbose_name='Zadnji ping')),
                ('heartbeat_count', models.IntegerField(default=0, verbose_name='Broj pingova')),
                ('is_active', models.BooleanField(default=True, verbose_name='Aktivna')),
                ('total_orders_claimed', models.IntegerField(default=0)),
                ('total_orders_delivered', models.IntegerField(default=0)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='waiter_shifts', to='companies.company', verbose_name='Tvrtka')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='waiter_shifts', to=settings.AUTH_USER_MODEL, verbose_name='Konobar')),
            ],
            options={
                'verbose_name': 'Smjena konobara',
                'verbose_name_plural': 'Smjene konobara',
                'ordering': ['-started_at'],
            },
        ),
    ]
