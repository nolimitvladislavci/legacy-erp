from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('synesis', '0006_alter_synesisexportqueue_export_type_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='synesisconfig',
            name='connect_base_path',
            field=models.CharField(
                blank=True,
                default=r'C:\SynesisConnect',
                help_text=r'Bazni folder za Connect radne kopije. Npr. C:\SynesisConnect',
                max_length=500,
                verbose_name='Connect bazni folder',
            ),
        ),
        migrations.AddField(
            model_name='synesisconfig',
            name='backup_retention_days',
            field=models.PositiveIntegerField(
                default=30,
                verbose_name='Čuvanje backupa (dana)',
            ),
        ),
        migrations.AddField(
            model_name='synesisconfig',
            name='auto_backup_enabled',
            field=models.BooleanField(
                default=True,
                verbose_name='Automatski backup prije synca',
            ),
        ),
        migrations.AddField(
            model_name='synesisconfig',
            name='last_backup_at',
            field=models.DateTimeField(
                null=True, blank=True,
                verbose_name='Zadnji backup',
            ),
        ),
        migrations.AddField(
            model_name='synesisconfig',
            name='last_backup_path',
            field=models.CharField(
                blank=True, default='',
                max_length=500,
                verbose_name='Putanja zadnjeg backupa',
            ),
        ),
        migrations.AddField(
            model_name='synesisconfig',
            name='last_sync_invoices',
            field=models.DateTimeField(
                null=True, blank=True,
                verbose_name='Zadnji sync faktura',
            ),
        ),
        migrations.AddField(
            model_name='synesisconfig',
            name='invoices_total',
            field=models.IntegerField(
                default=0,
                verbose_name='Ukupno faktura',
            ),
        ),
    ]
