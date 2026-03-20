from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('eracun', '0003_fiskalizacija_20_fields'),
    ]
    operations = [
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_type',
            field=models.CharField(max_length=30, blank=True, default='',
                choices=[
                    ('fina', 'FINA'),
                    ('moj_eracun', 'Moj-eRacun.hr'),
                    ('pondi', 'ePoslovanje (PONDI)'),
                    ('custom', 'Drugi posrednik'),
                ],
                verbose_name='Informacijski posrednik'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_api_url',
            field=models.URLField(blank=True, default='', verbose_name='API URL posrednika'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_api_key',
            field=models.CharField(max_length=200, blank=True, default='', verbose_name='API kljuc posrednika'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_api_secret',
            field=models.CharField(max_length=200, blank=True, default='', verbose_name='API secret posrednika'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_username',
            field=models.CharField(max_length=100, blank=True, default='', verbose_name='Korisnicko ime kod posrednika'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_password',
            field=models.CharField(max_length=200, blank=True, default='', verbose_name='Lozinka kod posrednika'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_company_id',
            field=models.CharField(max_length=50, blank=True, default='',
                verbose_name='ID firme kod posrednika',
                help_text='Peppol Participant ID ili interni ID kod posrednika'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_test_mode',
            field=models.BooleanField(default=True, verbose_name='Testni nacin (sandbox)'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_connected_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Spojeno na posrednika'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_status',
            field=models.CharField(max_length=20, blank=True, default='',
                choices=[
                    ('not_configured', 'Nije konfigurirano'),
                    ('testing', 'Testiranje'),
                    ('active', 'Aktivno'),
                    ('error', 'Greska'),
                ],
                verbose_name='Status veze s posrednikom'),
        ),
        migrations.AddField(
            model_name='eracunconfig',
            name='posrednik_raw_config',
            field=models.JSONField(default=dict, blank=True,
                verbose_name='Sirovi podaci konfiguracije',
                help_text='AI-parsirani podaci iz emaila/dokumenta posrednika'),
        ),
    ]
