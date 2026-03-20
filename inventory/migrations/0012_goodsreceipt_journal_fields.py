from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0011_add_primka_types_hr'),
        ('invoicing', '__first__'),
    ]

    operations = [
        migrations.AddField(
            model_name='goodsreceipt',
            name='invoice_due_date',
            field=models.DateField(blank=True, help_text='Kada se očekuje ulazni račun od dobavljača', null=True, verbose_name='Očekivani datum računa'),
        ),
        migrations.AddField(
            model_name='goodsreceipt',
            name='is_retail_valuation',
            field=models.BooleanField(default=False, help_text='Ako DA, knjiženje po MPC (3000/2200/3900). Ako NE, po nabavnoj (3000/1400/2200).', verbose_name='Maloprodajno zaduženje'),
        ),
        migrations.AddField(
            model_name='goodsreceipt',
            name='linked_invoice',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='goods_receipts', to='invoicing.invoice', verbose_name='Vezani ulazni račun'),
        ),
        migrations.AlterField(
            model_name='goodsreceipt',
            name='status',
            field=models.CharField(choices=[('draft', 'Nacrt'), ('confirmed', 'Potvrđena'), ('pending_invoice', 'Primljeno bez računa'), ('cancelled', 'Otkazana')], default='draft', max_length=20, verbose_name='Status'),
        ),
    ]
