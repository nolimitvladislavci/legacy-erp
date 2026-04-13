from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("companies", "0001_initial"),
        ("rental", "0001_initial"),
        ("inventory", "0001_initial"),
        ("marketplace", "0001_initial"),
        ("gastro_menu", "0001_initial"),
        ("pos", "0001_nkd_pos_integration"),
    ]

    operations = [
        # ── Experience ──
        migrations.CreateModel(
            name="Experience",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="Naziv")),
                ("slug", models.SlugField(blank=True, max_length=220, unique=True)),
                (
                    "experience_type",
                    models.CharField(
                        choices=[
                            ("degustacija", "Degustacija"),
                            ("radionica", "Radionica"),
                            ("berba", "Berba"),
                            ("tura", "Obilazak / Tura"),
                            ("jahanje", "Jahanje"),
                            ("promatranje", "Promatranje (golubi, ptice)"),
                            ("muznja", "Muznja"),
                            ("kulinarska", "Kulinarska radionica"),
                            ("wellness", "Wellness / Opuštanje"),
                            ("ostalo", "Ostalo"),
                        ],
                        max_length=20,
                        verbose_name="Tip",
                    ),
                ),
                ("description", models.TextField(blank=True, verbose_name="Opis")),
                ("what_to_bring", models.TextField(blank=True, verbose_name="Što ponijeti")),
                ("duration_minutes", models.PositiveIntegerField(verbose_name="Trajanje (min)")),
                ("capacity", models.PositiveIntegerField(verbose_name="Max gostiju")),
                ("min_pax", models.PositiveIntegerField(default=1, verbose_name="Min gostiju za održavanje")),
                (
                    "difficulty",
                    models.CharField(
                        choices=[
                            ("easy", "Lagano — za sve uzraste"),
                            ("medium", "Umjereno — potrebna obuća"),
                            ("hard", "Zahtjevno — fizička sprema"),
                        ],
                        default="easy",
                        max_length=10,
                    ),
                ),
                ("meeting_point", models.CharField(blank=True, max_length=300, verbose_name="Točka okupljanja")),
                ("gps_lat", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                ("gps_lng", models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True)),
                (
                    "price_per_person",
                    models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Cijena/osobi (EUR)"),
                ),
                ("child_discount_pct", models.PositiveIntegerField(default=50, verbose_name="Popust djeca (%)")),
                ("deposit_pct", models.PositiveIntegerField(default=30, verbose_name="Depozit (%)")),
                (
                    "cancellation_hours",
                    models.PositiveIntegerField(default=12, verbose_name="Besplatno otkazivanje (sati prije)"),
                ),
                (
                    "tax_rate",
                    models.DecimalField(decimal_places=2, default=25, max_digits=5, verbose_name="PDV stopa (%)"),
                ),
                (
                    "guide_languages",
                    models.CharField(blank=True, default="hr", max_length=100, verbose_name="Jezici vodstva"),
                ),
                ("image_main", models.ImageField(blank=True, null=True, upload_to="experiences/")),
                ("is_active", models.BooleanField(default=True)),
                ("seasonal_from", models.DateField(blank=True, null=True, verbose_name="Sezona od")),
                ("seasonal_until", models.DateField(blank=True, null=True, verbose_name="Sezona do")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="experiences",
                        to="companies.company",
                        verbose_name="OPG / Tvrtka",
                    ),
                ),
                (
                    "guide",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="guided_experiences",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Vodič",
                    ),
                ),
            ],
            options={
                "verbose_name": "Iskustvo / Aktivnost",
                "verbose_name_plural": "Iskustva / Aktivnosti",
                "ordering": ["name"],
            },
        ),
        # ── ExperienceSchedule ──
        migrations.CreateModel(
            name="ExperienceSchedule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField(verbose_name="Datum")),
                ("time_from", models.TimeField(verbose_name="Od")),
                ("time_to", models.TimeField(verbose_name="Do")),
                ("max_pax", models.PositiveIntegerField(verbose_name="Max gostiju")),
                ("booked_pax", models.PositiveIntegerField(default=0, verbose_name="Rezervirano")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Otvoreno za rezervacije"),
                            ("full", "Popunjeno"),
                            ("cancelled", "Otkazano"),
                            ("completed", "Završeno"),
                        ],
                        default="open",
                        max_length=15,
                    ),
                ),
                ("weather_note", models.CharField(blank=True, max_length=200, verbose_name="Vremenska napomena")),
                (
                    "experience",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="schedules",
                        to="experiences.experience",
                    ),
                ),
            ],
            options={
                "verbose_name": "Raspored iskustva",
                "verbose_name_plural": "Rasporedi iskustava",
                "ordering": ["date", "time_from"],
                "unique_together": {("experience", "date", "time_from")},
            },
        ),
        # ── ExperienceBooking ──
        migrations.CreateModel(
            name="ExperienceBooking",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("guest_name", models.CharField(max_length=200, verbose_name="Ime gosta")),
                ("guest_email", models.EmailField(blank=True, max_length=254)),
                ("guest_phone", models.CharField(blank=True, max_length=50)),
                ("guest_country", models.CharField(blank=True, max_length=3, verbose_name="Država (ISO)")),
                ("pax_count", models.PositiveIntegerField(verbose_name="Broj osoba")),
                ("children_count", models.PositiveIntegerField(default=0, verbose_name="Djece")),
                (
                    "price_total",
                    models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="Ukupna cijena"),
                ),
                (
                    "deposit_amount",
                    models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="Depozit"),
                ),
                ("deposit_paid", models.BooleanField(default=False)),
                ("deposit_paid_at", models.DateTimeField(blank=True, null=True)),
                (
                    "payment_method",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("card", "Kartica"),
                            ("cash", "Gotovina"),
                            ("transfer", "Virman"),
                            ("online", "Online uplata"),
                        ],
                        max_length=15,
                    ),
                ),
                ("remaining_paid", models.BooleanField(default=False, verbose_name="Ostatak plaćen")),
                ("deposit_forfeited", models.BooleanField(default=False, verbose_name="Depozit zadržan (no-show)")),
                (
                    "refund_amount",
                    models.DecimalField(decimal_places=2, default=0, max_digits=10, verbose_name="Povrat"),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Čeka uplatu depozita"),
                            ("confirmed", "Potvrđeno (depozit plaćen)"),
                            ("checked_in", "Prisutan"),
                            ("completed", "Završeno"),
                            ("no_show", "Nije se pojavio"),
                            ("cancelled", "Otkazano"),
                        ],
                        default="pending",
                        max_length=15,
                    ),
                ),
                ("notes", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "schedule",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="bookings",
                        to="experiences.experienceschedule",
                    ),
                ),
                (
                    "rental_booking",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="experience_bookings",
                        to="rental.booking",
                        verbose_name="Povezani smještaj",
                    ),
                ),
                (
                    "pos_receipt",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="experience_bookings",
                        to="pos.posreceipt",
                        verbose_name="POS račun",
                    ),
                ),
            ],
            options={
                "verbose_name": "Rezervacija iskustva",
                "verbose_name_plural": "Rezervacije iskustava",
                "ordering": ["-created_at"],
            },
        ),
        # ── ExperienceInclusion ──
        migrations.CreateModel(
            name="ExperienceInclusion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "description",
                    models.CharField(help_text='npr. "1 boca Šljivovice 0.5L"', max_length=200, verbose_name="Opis"),
                ),
                (
                    "quantity_per_person",
                    models.DecimalField(decimal_places=2, default=1, max_digits=8, verbose_name="Količina po osobi"),
                ),
                ("unit", models.CharField(default="kom", max_length=20, verbose_name="Jedinica")),
                (
                    "experience",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="inclusions",
                        to="experiences.experience",
                    ),
                ),
                (
                    "inventory_item",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="experience_inclusions",
                        to="inventory.inventoryitem",
                        verbose_name="Artikl iz skladišta",
                    ),
                ),
            ],
            options={"verbose_name": "Uključeno u iskustvo", "verbose_name_plural": "Uključeno u iskustva"},
        ),
        # ── ExperienceReview ──
        migrations.CreateModel(
            name="ExperienceReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("rating", models.PositiveIntegerField(verbose_name="Ocjena (1-5)")),
                ("text", models.TextField(blank=True, verbose_name="Komentar")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="experiences/reviews/")),
                ("is_public", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "booking",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="review",
                        to="experiences.experiencebooking",
                    ),
                ),
            ],
            options={
                "verbose_name": "Ocjena iskustva",
                "verbose_name_plural": "Ocjene iskustava",
                "ordering": ["-created_at"],
            },
        ),
        # ── AgroPackage ──
        migrations.CreateModel(
            name="AgroPackage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=200, verbose_name="Naziv paketa")),
                ("slug", models.SlugField(blank=True, max_length=220, unique=True)),
                ("description", models.TextField(blank=True)),
                ("image", models.ImageField(blank=True, null=True, upload_to="experiences/packages/")),
                (
                    "advertised_price",
                    models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Oglašena cijena (EUR)"),
                ),
                ("duration_days", models.PositiveIntegerField(default=1, verbose_name="Trajanje (dana)")),
                ("max_guests", models.PositiveIntegerField(default=2, verbose_name="Max gostiju")),
                ("is_active", models.BooleanField(default=True)),
                ("seasonal_from", models.DateField(blank=True, null=True)),
                ("seasonal_until", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="agro_packages",
                        to="companies.company",
                        verbose_name="OPG / Tvrtka",
                    ),
                ),
            ],
            options={"verbose_name": "Agro paket", "verbose_name_plural": "Agro paketi", "ordering": ["name"]},
        ),
        # ── PackageComponent ──
        migrations.CreateModel(
            name="PackageComponent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "component_type",
                    models.CharField(
                        choices=[
                            ("accommodation", "Smještaj"),
                            ("meal", "Obrok / Hrana"),
                            ("experience", "Aktivnost"),
                            ("product", "Proizvod"),
                            ("transport", "Prijevoz"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "label",
                    models.CharField(
                        help_text='npr. "2 noćenja u apartmanu Lavanda"', max_length=200, verbose_name="Naziv stavke"
                    ),
                ),
                (
                    "component_price",
                    models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Cijena komponente (EUR)"),
                ),
                ("tax_rate", models.DecimalField(decimal_places=2, max_digits=5, verbose_name="PDV stopa (%)")),
                ("quantity", models.PositiveIntegerField(default=1, verbose_name="Količina")),
                ("sort_order", models.PositiveIntegerField(default=0)),
                (
                    "package",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="components",
                        to="experiences.agropackage",
                    ),
                ),
                (
                    "property_link",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="package_components",
                        to="rental.property",
                        verbose_name="Smještaj",
                    ),
                ),
                (
                    "experience_link",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="package_components",
                        to="experiences.experience",
                        verbose_name="Aktivnost",
                    ),
                ),
                (
                    "marketplace_product_link",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="package_components",
                        to="marketplace.marketplaceproduct",
                        verbose_name="Proizvod s tržnice",
                    ),
                ),
                (
                    "menu_link",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="package_components",
                        to="gastro_menu.digitalmenu",
                        verbose_name="Meni / Obrok",
                    ),
                ),
            ],
            options={
                "verbose_name": "Komponenta paketa",
                "verbose_name_plural": "Komponente paketa",
                "ordering": ["sort_order"],
            },
        ),
        # ── RecallEvent ──
        migrations.CreateModel(
            name="RecallEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "source_model",
                    models.CharField(
                        help_text="npr. EggRecord, MedProizvodnja, StockBatch",
                        max_length=50,
                        verbose_name="Model izvora",
                    ),
                ),
                ("source_id", models.PositiveIntegerField(verbose_name="ID izvora")),
                ("lot_number", models.CharField(blank=True, max_length=100, verbose_name="Broj serije/šarže")),
                ("title", models.CharField(max_length=200, verbose_name="Naslov")),
                ("description", models.TextField(verbose_name="Opis problema")),
                (
                    "severity",
                    models.CharField(
                        choices=[
                            ("warning", "Upozorenje — praćenje"),
                            ("recall", "Povlačenje — ne konzumirati"),
                            ("critical", "Kritično — hitna obavijest"),
                        ],
                        default="warning",
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Otvoreno — istraga"),
                            ("investigating", "U tijeku — prikupljanje podataka"),
                            ("notified", "Obavijesti poslane"),
                            ("resolved", "Riješeno"),
                            ("false_alarm", "Lažna uzbuna"),
                        ],
                        default="open",
                        max_length=15,
                    ),
                ),
                ("affected_guests_count", models.PositiveIntegerField(default=0, verbose_name="Pogođenih gostiju")),
                ("affected_orders_count", models.PositiveIntegerField(default=0, verbose_name="Pogođenih narudžbi")),
                ("reported_symptoms", models.TextField(blank=True, verbose_name="Prijavljeni simptomi")),
                (
                    "health_authority_notified",
                    models.BooleanField(default=False, verbose_name="Sanitarna inspekcija obaviještena"),
                ),
                (
                    "health_authority_ref",
                    models.CharField(blank=True, max_length=100, verbose_name="Referenca prijave"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="recall_events",
                        to="companies.company",
                        verbose_name="Tvrtka",
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Prijavio",
                    ),
                ),
            ],
            options={
                "verbose_name": "Povlačenje proizvoda",
                "verbose_name_plural": "Povlačenja proizvoda",
                "ordering": ["-created_at"],
            },
        ),
        # ── RecallNotification ──
        migrations.CreateModel(
            name="RecallNotification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("whatsapp", "WhatsApp"),
                            ("email", "Email"),
                            ("sms", "SMS"),
                            ("push", "Push notifikacija"),
                        ],
                        max_length=10,
                    ),
                ),
                (
                    "recipient_type",
                    models.CharField(
                        help_text="npr. marketplace_buyer, rental_guest", max_length=30, verbose_name="Tip primatelja"
                    ),
                ),
                ("recipient_name", models.CharField(blank=True, max_length=200)),
                ("recipient_contact", models.CharField(max_length=200, verbose_name="Kontakt (tel/email)")),
                ("message", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Čeka slanje"),
                            ("sent", "Poslano"),
                            ("delivered", "Dostavljeno"),
                            ("failed", "Neuspjelo"),
                        ],
                        default="pending",
                        max_length=10,
                    ),
                ),
                ("sent_at", models.DateTimeField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "recall",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="notifications",
                        to="experiences.recallevent",
                    ),
                ),
            ],
            options={
                "verbose_name": "Obavijest o povlačenju",
                "verbose_name_plural": "Obavijesti o povlačenjima",
                "ordering": ["-created_at"],
            },
        ),
    ]
