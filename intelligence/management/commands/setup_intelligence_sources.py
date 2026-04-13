from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Kreira pocetne intelligence izvore (APPRRR, eKohezija, TISUP...)"

    def handle(self, *args, **kwargs):
        from intelligence.models import IntelligenceSource

        sources = [
            {
                "naziv": "APPRRR Natjecaji",
                "tip": "hr_poticaj",
                "url": "https://www.apprrr.hr/natjecaji/",
                "xpath_ili_opis": "Lista aktivnih natjecaja APPRRR agencije za OPG-ove. Trazi rokove, iznose, uvjete.",
                "provjeri_svakih_sati": 24,
            },
            {
                "naziv": "eKohezija EU fondovi",
                "tip": "eu_fond",
                "url": "https://razvoj.gov.hr/eu-fondovi/eu-fondovi-2021-2027/natjecaji/531",
                "xpath_ili_opis": "EU fondovi HR 2021-2027 otvoreni natjecaji. Fokus na ruralni razvoj, EAFRD, ESF+.",
                "provjeri_svakih_sati": 24,
            },
            {
                "naziv": "Ministarstvo poljoprivrede natjecaji",
                "tip": "hr_poticaj",
                "url": "https://poljoprivreda.gov.hr/istaknute-teme/natjecaji-i-javni-pozivi-116/116",
                "xpath_ili_opis": "Lista natjecaja Ministarstva poljoprivrede HR. OPG, stocarstvo, bio certifikacija.",
                "provjeri_svakih_sati": 24,
            },
            {
                "naziv": "Agroklub vijesti",
                "tip": "vijest",
                "url": "https://www.agroklub.com/vijesti/",
                "xpath_ili_opis": "Agro vijesti HR. Trzisne cijene, subvencije, upute, regulative.",
                "provjeri_svakih_sati": 12,
            },
            {
                "naziv": "TISUP trzisne cijene",
                "tip": "trzisna_cijena",
                "url": "https://www.tisup.hr/tr.aspx",
                "xpath_ili_opis": "Trzisno informacijski sustav TISUP. Cijene kukuruza, psenice, soje po tjednu.",
                "provjeri_svakih_sati": 6,
            },
            {
                "naziv": "HAPIH bio certifikacija",
                "tip": "bio_certifikacija",
                "url": "https://www.hapih.hr/ekoloska-proizvodnja/",
                "xpath_ili_opis": "Uvjeti za ekolosku certifikaciju u HR. Zahtjevi, rokovi, dokumentacija.",
                "provjeri_svakih_sati": 168,
            },
        ]

        created = 0
        for s in sources:
            obj, c = IntelligenceSource.objects.get_or_create(
                url=s["url"],
                defaults=s,
            )
            if c:
                created += 1
                self.stdout.write(f"  Kreiran: {obj.naziv}")
            else:
                self.stdout.write(f"  Postoji: {obj.naziv}")

        self.stdout.write(f"\nUkupno novih: {created}/{len(sources)}")
