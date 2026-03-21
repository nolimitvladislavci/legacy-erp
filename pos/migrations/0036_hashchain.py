"""
Migration 0036: Hash Chain — kriptografski audit trail.
ChainLink model za nepromjenjiv lanac transakcija unutar PostgreSQL-a.
"""
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0035_training_partial_pulse'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChainLink',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('company', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                    related_name='chain_links', to='companies.company')),
                ('sequence', models.PositiveBigIntegerField(db_index=True)),
                ('receipt', models.OneToOneField(on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True, related_name='chain_link', to='pos.posreceipt')),
                ('payload_hash', models.CharField(max_length=64, verbose_name='SHA256 payload')),
                ('prev_hash', models.CharField(max_length=64, verbose_name='Hash prethodne karike')),
                ('chain_hash', models.CharField(max_length=64, unique=True, verbose_name='Hash ove karike')),
                ('payload_summary', models.CharField(max_length=200, blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Hash Chain Link',
                'verbose_name_plural': 'Hash Chain Links',
                'ordering': ['company', 'sequence'],
                'unique_together': {('company', 'sequence')},
            },
        ),
    ]
