"""
Migration 0039: Global receipt number — jedinstven po firmi, bez duplikata.
Kao Synesis: redni brojevi idu redom bez obzira na smjenu.
"""
from django.db import migrations, models


def backfill_global_numbers(apps, schema_editor):
    """Dodijeli global_number svim postojećim receiptima po firmi, kronološki."""
    POSReceipt = apps.get_model('pos', 'POSReceipt')
    from django.db.models import F

    # Group by company (via terminal)
    company_ids = set(
        POSReceipt.objects.values_list(
            'session__terminal__company_id', flat=True
        ).distinct()
    )

    for cid in company_ids:
        receipts = POSReceipt.objects.filter(
            session__terminal__company_id=cid
        ).order_by('created_at', 'pk')

        for idx, r in enumerate(receipts, 1):
            POSReceipt.objects.filter(pk=r.pk).update(global_number=idx)


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0038_restore_chainlink'),
    ]

    operations = [
        migrations.AddField(
            model_name='posreceipt',
            name='global_number',
            field=models.PositiveIntegerField(
                null=True, blank=True, db_index=True,
                verbose_name='Globalni redni broj',
                help_text='Jedinstven po firmi, bez duplikata. Za fiskalizaciju.',
            ),
        ),
        migrations.RunPython(backfill_global_numbers, migrations.RunPython.noop),
    ]
