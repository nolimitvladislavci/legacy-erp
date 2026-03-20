from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eracun', '0002_eracun_inbox_support'),
    ]

    operations = [
        # KPD code on line items (Klasifikacija Proizvoda i Djelatnosti)
        migrations.AddField(
            model_name='eracunitem',
            name='kpd_code',
            field=models.CharField(
                max_length=20, blank=True, default='',
                verbose_name='KPD 2025 sifra',
                help_text='Klasifikacija proizvoda i djelatnosti (obavezno od 2026)',
            ),
        ),

        # ERacun status workflow for Fiskalizacija 2.0
        migrations.AddField(
            model_name='eracun',
            name='posrednik',
            field=models.CharField(
                max_length=30, blank=True, default='',
                choices=[
                    ('fina', 'FINA'),
                    ('moj_eracun', 'Moj-eRacun'),
                    ('pondi', 'ePoslovanje (PONDI)'),
                    ('direct', 'Direktno (vlastiti cert)'),
                ],
                verbose_name='Informacijski posrednik',
            ),
        ),
        migrations.AddField(
            model_name='eracun',
            name='posrednik_id',
            field=models.CharField(
                max_length=100, blank=True, default='',
                verbose_name='ID kod posrednika',
                help_text='Referentni broj koji posrednik dodjeljuje',
            ),
        ),
        migrations.AddField(
            model_name='eracun',
            name='posrednik_status',
            field=models.CharField(
                max_length=20, blank=True, default='',
                choices=[
                    ('pending', 'Na cekanju'),
                    ('sent', 'Poslano posredniku'),
                    ('delivered', 'Dostavljeno primatelju'),
                    ('accepted', 'Prihvaceno'),
                    ('rejected', 'Odbijeno'),
                    ('paid', 'Naplaceno'),
                    ('error', 'Greska'),
                ],
                verbose_name='Status kod posrednika',
            ),
        ),
        migrations.AddField(
            model_name='eracun',
            name='posrednik_response',
            field=models.JSONField(
                default=dict, blank=True,
                verbose_name='Odgovor posrednika (JSON)',
            ),
        ),
    ]
