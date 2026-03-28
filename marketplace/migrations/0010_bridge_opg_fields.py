from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0009_product_fragile_heavy'),
    ]

    operations = [
        migrations.AddField(
            model_name='marketplaceproduct',
            name='opg_number',
            field=models.CharField(blank=True, help_text='Obavezno za prehrambene proizvode — Zakon o OPG čl.12', max_length=50, verbose_name='OPG broj'),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='disclaimer_text',
            field=models.TextField(blank=True, default='Proizvod dolazi izravno s OPG-a. Prije konzumacije provjerite alergene i rok trajanja.', verbose_name='Disclaimer'),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='source_model',
            field=models.CharField(blank=True, help_text='npr. EggRecord, MedProizvodnja', max_length=50, verbose_name='Izvorni model'),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='source_id',
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name='Izvorni ID'),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='auto_listed',
            field=models.BooleanField(default=False, verbose_name='Auto-objavljeno'),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='expires_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Istječe'),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='delivery_zone_km',
            field=models.PositiveIntegerField(blank=True, help_text='Geofencing za kvarljive proizvode', null=True, verbose_name='Zona dostave (km)'),
        ),
        migrations.AddIndex(
            model_name='marketplaceproduct',
            index=models.Index(fields=['source_model', 'source_id'], name='mkt_source_idx'),
        ),
        migrations.AddIndex(
            model_name='marketplaceproduct',
            index=models.Index(fields=['auto_listed', 'expires_at'], name='mkt_autolist_expiry_idx'),
        ),
    ]
