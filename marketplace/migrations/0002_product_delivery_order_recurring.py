"""Add delivery_fee to MarketplaceProduct, recurring fields to MarketplaceOrder."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0001_initial'),
    ]

    operations = [
        # Delivery fee per product (each seller sets their own)
        migrations.AddField(
            model_name='marketplaceproduct',
            name='delivery_fee_per_unit',
            field=models.DecimalField(
                max_digits=8, decimal_places=2, default=0,
                verbose_name='Dostava po jedinici',
                help_text='Cijena dostave po jedinici (kg/kom). 0 = besplatna.',
            ),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='free_delivery_above',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, null=True, blank=True,
                verbose_name='Besplatna dostava iznad',
                help_text='Besplatna dostava za narudzbe iznad ovog iznosa.',
            ),
        ),
        migrations.AddField(
            model_name='marketplaceproduct',
            name='pickup_available',
            field=models.BooleanField(default=True, verbose_name='Osobno preuzimanje'),
        ),
        # Recurring orders
        migrations.AddField(
            model_name='marketplaceorder',
            name='is_recurring',
            field=models.BooleanField(default=False, verbose_name='Ponavljajuca narudzba'),
        ),
        migrations.AddField(
            model_name='marketplaceorder',
            name='recurring_interval',
            field=models.CharField(
                max_length=20, blank=True, default='',
                choices=[
                    ('daily', 'Dnevno'),
                    ('weekly', 'Tjedno'),
                    ('biweekly', 'Svaka 2 tjedna'),
                    ('monthly', 'Mjesecno'),
                ],
                verbose_name='Interval ponavljanja',
            ),
        ),
        migrations.AddField(
            model_name='marketplaceorder',
            name='recurring_source',
            field=models.ForeignKey(
                to='marketplace.MarketplaceOrder',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True,
                related_name='recurring_copies',
                verbose_name='Izvorna ponavljajuca narudzba',
            ),
        ),
        migrations.AddField(
            model_name='marketplaceorder',
            name='next_recurring_date',
            field=models.DateField(null=True, blank=True, verbose_name='Sljedece ponavljanje'),
        ),
    ]
