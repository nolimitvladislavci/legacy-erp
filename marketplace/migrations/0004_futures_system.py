"""Futures / Pre-harvest reservation system."""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('marketplace', '0003_discount_system'),
        ('companies', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FuturesListing',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('seller_company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='futures_listings',
                    to='companies.company',
                    verbose_name='Prodavac (OPG)',
                )),
                ('product', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    related_name='futures_listings',
                    to='marketplace.marketplaceproduct',
                    verbose_name='Povezani proizvod',
                )),
                ('category', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    to='marketplace.marketplacecategory',
                )),
                ('name', models.CharField(max_length=200, verbose_name='Naziv')),
                ('description', models.TextField(blank=True)),
                ('unit', models.CharField(max_length=20, default='kg')),
                ('unit_price', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    verbose_name='Garantirana cijena po jedinici',
                )),
                ('total_capacity', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    verbose_name='Ukupni kapacitet',
                )),
                ('reserved_qty', models.DecimalField(
                    max_digits=10, decimal_places=2, default=0,
                    verbose_name='Rezervirano',
                )),
                ('min_order_qty', models.DecimalField(
                    max_digits=10, decimal_places=2, default=1,
                    verbose_name='Min. narudzba',
                )),
                ('available_from', models.DateField(verbose_name='Dostupno od')),
                ('available_until', models.DateField(verbose_name='Dostupno do')),
                ('booking_deadline', models.DateField(
                    verbose_name='Rok za rezervaciju',
                    help_text='Nakon ovog datuma vise se ne moze rezervirati.',
                )),
                ('deposit_percent', models.DecimalField(
                    max_digits=5, decimal_places=2, default=20,
                    verbose_name='Avans %',
                    help_text='Postotak koji kupac placa odmah pri rezervaciji.',
                )),
                ('origin_region', models.CharField(max_length=100, blank=True, verbose_name='Regija')),
                ('is_organic', models.BooleanField(default=False)),
                ('requires_cold_chain', models.BooleanField(default=False)),
                ('status', models.CharField(
                    max_length=20, default='open',
                    choices=[
                        ('draft', 'Nacrt'),
                        ('open', 'Otvoreno za rezervacije'),
                        ('fully_booked', 'Potpuno rezervirano'),
                        ('harvesting', 'U berbi / pripremi'),
                        ('delivering', 'Isporuka u tijeku'),
                        ('completed', 'Zavrseno'),
                        ('cancelled', 'Otkazano'),
                    ],
                )),
                ('image', models.ImageField(upload_to='marketplace/futures/', blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Futures ponuda',
                'verbose_name_plural': 'Futures ponude',
                'ordering': ['available_from', '-created_at'],
            },
        ),

        migrations.CreateModel(
            name='FuturesReservation',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('listing', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reservations',
                    to='marketplace.futureslisting',
                )),
                ('buyer_company', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='futures_reservations',
                    to='companies.company',
                )),
                ('buyer_user', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    null=True, blank=True,
                    to='auth.user',
                )),
                ('quantity', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    verbose_name='Rezervirana kolicina',
                )),
                ('unit_price', models.DecimalField(
                    max_digits=10, decimal_places=2,
                    verbose_name='Garantirana cijena',
                )),
                ('total_price', models.DecimalField(
                    max_digits=12, decimal_places=2, default=0,
                )),
                ('deposit_amount', models.DecimalField(
                    max_digits=12, decimal_places=2, default=0,
                    verbose_name='Iznos avansa',
                )),
                ('deposit_paid', models.BooleanField(default=False, verbose_name='Avans placen')),
                ('deposit_paid_at', models.DateTimeField(null=True, blank=True)),
                ('delivery_preference', models.CharField(
                    max_length=20, default='delivery',
                    choices=[
                        ('delivery', 'Dostava'),
                        ('pickup', 'Osobno preuzimanje'),
                        ('bus', 'Bus linija'),
                        ('courier', 'Kurir'),
                    ],
                )),
                ('delivery_address', models.CharField(max_length=300, blank=True)),
                ('delivery_notes', models.TextField(blank=True)),
                ('recurring_weekly', models.BooleanField(
                    default=False,
                    verbose_name='Tjedna isporuka',
                    help_text='Podijeli ukupnu kolicinu na tjedne isporuke.',
                )),
                ('status', models.CharField(
                    max_length=20, default='pending',
                    choices=[
                        ('pending', 'Ceka potvrdu'),
                        ('confirmed', 'Potvrdeno'),
                        ('deposit_paid', 'Avans placen'),
                        ('ready', 'Roba spremna'),
                        ('partially_delivered', 'Djelomicno isporuceno'),
                        ('delivered', 'Isporuceno'),
                        ('completed', 'Zavrseno'),
                        ('cancelled', 'Otkazano'),
                    ],
                )),
                ('discount_percent', models.DecimalField(
                    max_digits=5, decimal_places=2, default=0,
                    verbose_name='Rabat %',
                    help_text='Early-bird ili partnerski rabat na futures cijenu.',
                )),
                ('confirmed_at', models.DateTimeField(null=True, blank=True)),
                ('delivered_qty', models.DecimalField(
                    max_digits=10, decimal_places=2, default=0,
                    verbose_name='Isporucena kolicina',
                )),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('notes', models.TextField(blank=True)),
            ],
            options={
                'verbose_name': 'Futures rezervacija',
                'verbose_name_plural': 'Futures rezervacije',
                'ordering': ['-created_at'],
            },
        ),

        # Delivery schedule for recurring weekly splits
        migrations.CreateModel(
            name='FuturesDeliverySlot',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('reservation', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='delivery_slots',
                    to='marketplace.futuresreservation',
                )),
                ('scheduled_date', models.DateField(verbose_name='Planirani datum')),
                ('quantity', models.DecimalField(max_digits=10, decimal_places=2)),
                ('status', models.CharField(
                    max_length=20, default='scheduled',
                    choices=[
                        ('scheduled', 'Planirano'),
                        ('ready', 'Spremno'),
                        ('shipped', 'Poslano'),
                        ('delivered', 'Isporuceno'),
                        ('skipped', 'Preskoceno'),
                    ],
                )),
                ('delivered_at', models.DateTimeField(null=True, blank=True)),
                ('tracking_number', models.CharField(max_length=100, blank=True)),
            ],
            options={
                'verbose_name': 'Futures isporuka',
                'verbose_name_plural': 'Futures isporuke',
                'ordering': ['scheduled_date'],
            },
        ),
    ]
