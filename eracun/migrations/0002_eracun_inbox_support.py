from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('eracun', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='eracun',
            name='direction',
            field=models.CharField(
                max_length=10,
                choices=[('outgoing', 'Izlazni'), ('incoming', 'Ulazni')],
                default='outgoing',
                verbose_name='Smjer',
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name='eracun',
            name='original_xml',
            field=models.TextField(blank=True, verbose_name='Originalni UBL XML'),
        ),
        migrations.AddField(
            model_name='eracun',
            name='received_at',
            field=models.DateTimeField(null=True, blank=True, verbose_name='Primljeno'),
        ),
        migrations.AddField(
            model_name='eracun',
            name='received_via',
            field=models.CharField(
                max_length=20, blank=True, default='',
                choices=[
                    ('api', 'API'),
                    ('email', 'Email'),
                    ('upload', 'Rucni upload'),
                    ('peppol', 'PEPPOL mreza'),
                    ('fina', 'FINA servis'),
                ],
                verbose_name='Primljeno putem',
            ),
        ),
        migrations.AddField(
            model_name='eracun',
            name='is_booked',
            field=models.BooleanField(default=False, verbose_name='Proknjizeno u URA'),
        ),
        migrations.AddField(
            model_name='eracun',
            name='booked_invoice',
            field=models.ForeignKey(
                to='invoicing.Invoice',
                on_delete=models.SET_NULL,
                null=True, blank=True,
                related_name='incoming_eracun',
                verbose_name='Proknjizena faktura',
            ),
        ),
        migrations.AlterField(
            model_name='eracun',
            name='invoice',
            field=models.OneToOneField(
                to='invoicing.Invoice',
                on_delete=models.SET_NULL,
                null=True, blank=True,
                related_name='outgoing_eracun',
                verbose_name='Izlazna faktura',
            ),
        ),
    ]
