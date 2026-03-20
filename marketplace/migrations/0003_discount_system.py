"""Add discount/rebate system to marketplace."""
from decimal import Decimal
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0002_product_delivery_order_recurring'),
        ('companies', '0001_initial'),
    ]

    operations = [
        # ── Partner Tier (Bronze/Silver/Gold) ──
        migrations.CreateModel(
            name='PartnerDiscount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('seller_company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='partner_discounts_given',
                    to='companies.company',
                    verbose_name='Prodavac',
                )),
                ('buyer_company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='partner_discounts_received',
                    to='companies.company',
                    verbose_name='Kupac',
                )),
                ('tier', models.CharField(
                    max_length=20, default='standard',
                    choices=[
                        ('standard', 'Standard (0%)'),
                        ('bronze', 'Bronze (10%)'),
                        ('silver', 'Silver (15%)'),
                        ('gold', 'Gold (20%)'),
                        ('platinum', 'Platinum (25%)'),
                        ('custom', 'Custom'),
                    ],
                    verbose_name='Partnerski tier',
                )),
                ('discount_percent', models.DecimalField(
                    max_digits=5, decimal_places=2, default=0,
                    verbose_name='Rabat %',
                    help_text='Generalni rabat na sve artikle. Za tier!=custom, automatski se postavlja.',
                )),
                ('is_active', models.BooleanField(default=True)),
                ('valid_from', models.DateField(null=True, blank=True)),
                ('valid_until', models.DateField(null=True, blank=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Partnerski rabat',
                'verbose_name_plural': 'Partnerski rabati',
                'unique_together': {('seller_company', 'buyer_company')},
            },
        ),

        # ── Category Discount (per seller-buyer-category) ──
        migrations.CreateModel(
            name='CategoryDiscount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('seller_company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='category_discounts_given',
                    to='companies.company',
                )),
                ('buyer_company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    null=True, blank=True,
                    related_name='category_discounts_received',
                    to='companies.company',
                    help_text='Prazno = vrijedi za sve kupce.',
                )),
                ('category', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    to='marketplace.marketplacecategory',
                    verbose_name='Kategorija',
                )),
                ('discount_percent', models.DecimalField(
                    max_digits=5, decimal_places=2, default=0,
                    verbose_name='Rabat %',
                )),
                ('is_active', models.BooleanField(default=True)),
                ('valid_from', models.DateField(null=True, blank=True)),
                ('valid_until', models.DateField(null=True, blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Rabat po kategoriji',
                'verbose_name_plural': 'Rabati po kategorijama',
            },
        ),

        # ── Volume Discount (quantity breaks) ──
        migrations.CreateModel(
            name='VolumeDiscount',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('seller_company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='volume_discounts',
                    to='companies.company',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    null=True, blank=True,
                    related_name='volume_discounts',
                    to='marketplace.marketplaceproduct',
                    help_text='Prazno = vrijedi za sve artikle ovog prodavaca.',
                )),
                ('category', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    null=True, blank=True,
                    to='marketplace.marketplacecategory',
                    help_text='Prazno = sve kategorije.',
                )),
                ('min_quantity', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    verbose_name='Min. kolicina',
                )),
                ('discount_percent', models.DecimalField(
                    max_digits=5, decimal_places=2, default=0,
                    verbose_name='Rabat %',
                )),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Kolicinski rabat',
                'verbose_name_plural': 'Kolicinski rabati',
                'ordering': ['seller_company', 'min_quantity'],
            },
        ),

        # ── Discount fields on OrderItem ──
        migrations.AddField(
            model_name='marketplaceorderitem',
            name='discount_percent',
            field=models.DecimalField(
                max_digits=5, decimal_places=2, default=0,
                verbose_name='Rabat %',
            ),
        ),
        migrations.AddField(
            model_name='marketplaceorderitem',
            name='discount_amount',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                verbose_name='Iznos rabata',
            ),
        ),
        migrations.AddField(
            model_name='marketplaceorderitem',
            name='original_price',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                verbose_name='Maloprodajna cijena',
            ),
        ),
    ]
