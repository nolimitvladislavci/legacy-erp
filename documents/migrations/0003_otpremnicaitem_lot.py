from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0002_process_documents'),
        ('pos', '0010_voucher'),
    ]

    operations = [
        migrations.AddField(
            model_name='otpremnicaitem',
            name='batch_number',
            field=models.CharField(
                blank=True, max_length=50,
                verbose_name='LOT / Šarža',
                help_text='Npr. LOT-20261015 — iz kojeg prešanja/berbe je roba',
            ),
        ),
        migrations.AddField(
            model_name='otpremnicaitem',
            name='expiry_batch',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='otpremnica_items',
                to='pos.expirybatch',
                verbose_name='Veza na LOT (ExpiryBatch)',
            ),
        ),
    ]
