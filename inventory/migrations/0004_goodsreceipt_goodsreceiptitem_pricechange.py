from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_inventoryitem_image_webshop'),
        ('companies', '0001_initial'),
        ('partners', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [
        migrations.CreateModel(
            name='GoodsReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('receipt_number', models.CharField(blank=True, max_length=50, verbose_name='Broj primke')),
                ('date', models.DateField(verbose_name='Datum primke')),
                ('document_number', models.CharField(blank=True, max_length=100, verbose_name='Broj dostavnice/fakture')),
                ('status', models.CharField(choices=[('draft', 'Nacrt'), ('confirmed', 'Potvrđena'), ('cancelled', 'Otkazana')], default='draft', max_length=20, verbose_name='Status')),
                ('notes', models.TextField(blank=True, verbose_name='Napomene')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('total_purchase', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Ukupna nabavna vrijednost')),
                ('total_selling', models.DecimalField(decimal_places=2, default=0, max_digits=12, verbose_name='Ukupna prodajna vrijednost')),
                ('company', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='companies.company', verbose_name='Tvrtka')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user', verbose_name='Kreirao')),
                ('supplier', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='goods_receipts', to='partners.partner', verbose_name='Dobavljač')),
            ],
            options={
                'verbose_name': 'Primka',
                'verbose_name_plural': 'Primke',
                'ordering': ['-date', '-created_at'],
            },
        ),
        migrations.CreateModel(
            name='GoodsReceiptItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, default=1, max_digits=10, verbose_name='Količina')),
                ('purchase_price_unit', models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='Nabavna cijena/jed.')),
                ('dependent_costs_unit', models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='Zavisni troškovi/jed.')),
                ('cost_price_unit', models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='Nabavna cijena s troš.')),
                ('margin_percent', models.DecimalField(decimal_places=2, default=0, max_digits=6, verbose_name='Marža (%)')),
                ('margin_amount', models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='Iznos marže')),
                ('selling_price_net', models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='Prodajna cijena bez PDV')),
                ('tax_rate', models.DecimalField(decimal_places=2, default=25, max_digits=5, verbose_name='PDV stopa (%)')),
                ('selling_price_vat', models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='Iznos PDV-a')),
                ('selling_price_gross', models.DecimalField(decimal_places=4, default=0, max_digits=12, verbose_name='MPC (s PDV-om)')),
                ('total_purchase_price', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Uk. nabavna')),
                ('total_cost_price', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Uk. nabavna s troš.')),
                ('total_selling_gross', models.DecimalField(decimal_places=2, default=0, max_digits=14, verbose_name='Uk. MPC')),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='inventory.inventoryitem', verbose_name='Artikl')),
                ('receipt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='inventory.goodsreceipt', verbose_name='Primka')),
            ],
            options={
                'verbose_name': 'Stavka primke',
                'verbose_name_plural': 'Stavke primke',
            },
        ),
        migrations.CreateModel(
            name='PriceChange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('old_purchase_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Stara nabavna')),
                ('new_purchase_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Nova nabavna')),
                ('old_unit_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Stara prodajna')),
                ('new_unit_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Nova prodajna')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='auth.user', verbose_name='Promijenio')),
                ('goods_receipt', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='inventory.goodsreceipt', verbose_name='Primka')),
                ('inventory_item', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='price_changes', to='inventory.inventoryitem', verbose_name='Artikl')),
            ],
            options={
                'verbose_name': 'Promjena cijene',
                'verbose_name_plural': 'Promjene cijena',
                'ordering': ['-created_at'],
            },
        ),
    ]
