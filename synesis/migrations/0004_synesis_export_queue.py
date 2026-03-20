"""Add SynesisExportQueue for reverse sync ERP → Synesis."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('synesis', '0003_synesisconfig_last_sync_pos_and_more'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='SynesisExportQueue',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='synesis_exports',
                    to='companies.company',
                )),
                ('export_type', models.CharField(
                    max_length=20,
                    choices=[('item', 'Artikl'), ('partner', 'Partner')],
                )),
                ('action', models.CharField(
                    max_length=10,
                    choices=[('update', 'Update'), ('insert', 'Insert')],
                    default='update',
                )),
                ('synesis_id', models.CharField(
                    max_length=50, blank=True, default='',
                    help_text='Synesis ITEM_ID or PARTNER_ID for updates.',
                )),
                ('erp_object_id', models.CharField(
                    max_length=50, blank=True, default='',
                    help_text='ERP InventoryItem.pk or Partner.pk',
                )),
                ('payload', models.JSONField(
                    default=dict,
                    help_text='Fields to write to MDB: {"ITEM_PRICE": 5.50, ...}',
                )),
                ('description', models.CharField(max_length=300, blank=True)),
                ('is_exported', models.BooleanField(default=False)),
                ('exported_at', models.DateTimeField(null=True, blank=True)),
                ('is_confirmed', models.BooleanField(default=False)),
                ('confirmed_at', models.DateTimeField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('created_by', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    to='auth.user',
                )),
            ],
            options={
                'verbose_name': 'Synesis export red',
                'verbose_name_plural': 'Synesis export red',
                'ordering': ['-created_at'],
            },
        ),
    ]
