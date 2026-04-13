"""
Seed 8 compliance artikala za azil + 3 drona fix zapisa.

Usage:
    python manage.py seed_azil_compliance
    python manage.py seed_azil_compliance --company-id 123
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

COMPLIANCE_ARTICLES = [
    {
        "law_reference": "Zakon o za\u0161titi \u017eivotinja (NN 102/17) \u010dl. 55",
        "description": "Zabrana usmr\u0107ivanja zdravih \u017eivotinja u skloni\u0161tu. "
        "Eutanazija isklju\u010divo veterinarskom odlukom za neizlje\u010divo bolesne/te\u0161ko ozlije\u0111ene.",
        "status": "compliant",
        "ai_notes": "Model VeterinarskaEutanazija zahtijeva dijagnozu i OIB veterinara. "
        "View role_check ograni\u010dava pristup.",
    },
    {
        "law_reference": "Zakon o za\u0161titi \u017eivotinja (NN 102/17) \u010dl. 62",
        "description": "Obvezni mjese\u010dni izvje\u0161taj skloni\u0161ta za JLS. "
        "Sadr\u017eaj: primljeno, udomljeno, vra\u0107eno, uginulo, eutanazirano, trenutno stanje, tro\u0161kovi.",
        "status": "compliant",
        "ai_notes": "MjesecniIzvjestajAzil model + Celery task generate_azil_monthly_report. "
        "Automatski PDF 1. u mjesecu.",
    },
    {
        "law_reference": "Zakon o za\u0161titi \u017eivotinja (NN 102/17) \u010dl. 48",
        "description": "Obavezna karantena 15 dana za novoprispjele \u017eivotinje. "
        "Veterinarski pregled pri primitku, cijepljenje i antiparazitik.",
        "status": "compliant",
        "ai_notes": "Model Zivotinja automatski ra\u010duna datum_karantena_kraj (datum_ulaska + 15 dana). "
        "Status workflow: karantena \u2192 slobodan \u2192 rezerviran \u2192 udomljen.",
    },
    {
        "law_reference": "Zakon o za\u0161titi \u017eivotinja (NN 102/17) \u010dl. 51",
        "description": "Obvezno mikro\u010dipiranje pasa u skloni\u0161tu (ISO 11784). "
        "Upis u Jedinstveni upisnik ku\u0107nih ljubimaca (JUKL).",
        "status": "compliant",
        "ai_notes": "Polje mikrocip na modelu Zivotinja. Web Bluetooth \u010dita\u010d u terenskoj formi. "
        "API azil_chip_lookup za provjeru.",
    },
    {
        "law_reference": "Zakon o za\u0161titi \u017eivotinja (NN 102/17) \u010dl. 52",
        "description": "Ugovor o udomljavanju s OIB-om udomitelja. "
        "Pra\u0107enje udomljenih \u017eivotinja min. 1 godinu.",
        "status": "compliant",
        "ai_notes": "Model Udomljavanje zahtijeva OIB, adresu, telefon. "
        "Polje ugovor_potpisan = boolean. Tip: trajno/privremeno/povrat.",
    },
    {
        "law_reference": "Pravilnik o uvjetima skloni\u0161ta (NN 99/19) \u010dl. 8",
        "description": "Evidencijski broj za svaku \u017eivotinju po formatu AZ-YYYY-NNNN. "
        "Karton zdravlja s tretmanima, veterinar, tro\u0161kovi.",
        "status": "compliant",
        "ai_notes": "Zivotinja.save() auto-generira evidencijski_br. KartonZdravlja model pokriva sve tipove tretmana.",
    },
    {
        "law_reference": "GDPR \u010dl. 6(1)(c) + HR ZVOP",
        "description": "Obrada OIB-a udomitelja i veterinara = zakonska obveza (ZoZ\u017d). "
        "Pravna osnova: ispunjavanje pravne obveze voditelja obrade.",
        "status": "compliant",
        "ai_notes": "OIB polja su zakonski obvezna (ZoZ\u017d cl. 52). "
        "Multi-tenant izolacija putem CompanyManager sprje\u010dava cross-tenant curenje.",
    },
    {
        "law_reference": "Zakon o za\u0161titi \u017eivotinja (NN 102/17) \u010dl. 46",
        "description": "Terenske intervencije hvatanja napu\u0161tenih \u017eivotinja. "
        "Evidencija: datum, lokacija (GPS), broj \u017eivotinja, rezultat, djelatnik.",
        "status": "compliant",
        "ai_notes": "Model AzilIntervencija s GPS, km, broj_zivotinja, rezultat. "
        "Terenska forma s camera capture i geolokacijom.",
    },
]

DRONE_FIXES = [
    {
        "law_reference": "GDPR Multi-tenant izolacija \u2014 Dron #1 fix",
        "description": "ChainLink (pos/hashchain.py) dodan CompanyManager. "
        "Prije: fiskalni hash lanac bio \u010ditljiv cross-tenant. "
        "Fix: objects = CompanyManager() \u2014 2 linije.",
        "status": "compliant",
        "ai_notes": "Gemini adversarijalni review identificirao. Fixano 2026-04-02.",
    },
    {
        "law_reference": "GDPR Multi-tenant izolacija \u2014 Dron #1 fix",
        "description": "GovExport (gov_export/models.py) dodan CompanyManager. "
        "Prije: porezni exporti bili cross-tenant \u010ditljivi. "
        "Fix: objects = CompanyManager() \u2014 2 linije.",
        "status": "compliant",
        "ai_notes": "Gemini adversarijalni review identificirao. Fixano 2026-04-02.",
    },
    {
        "law_reference": "Django URL namespace fix \u2014 Dron #3 prevencija",
        "description": "Azil view redirecti koristili URL name bez namespace prefiksa udruge:. "
        'Fix: redirect("azil_dashboard") \u2192 redirect("udruge:azil_dashboard"). '
        "4 redirect poziva popravljeno.",
        "status": "compliant",
        "ai_notes": "Preventivni fix. Bez ovoga redirect bi pao s NoReverseMatch na produkciji.",
    },
]


class Command(BaseCommand):
    help = "Seed 8 azil compliance artikala + 3 drona fix zapisa"

    def add_arguments(self, parser):
        parser.add_argument("--company-id", type=int, help="Specific company ID")

    def handle(self, *args, **options):
        from companies.models import Company
        from limit_connect_ai.models import ComplianceWatchItem

        if options["company_id"]:
            companies = Company.objects.filter(pk=options["company_id"])
        else:
            # Sve firme koje imaju azil zivotinje, ili prva aktivna
            from udruge.models import Zivotinja

            company_ids = Zivotinja.objects.unscoped().values_list("company_id", flat=True).distinct()
            if company_ids:
                companies = Company.objects.filter(pk__in=company_ids)
            else:
                companies = Company.objects.filter(is_deactivated=False)[:1]

        if not companies.exists():
            self.stderr.write("Nema aktivnih firmi.")
            return

        total_created = 0
        for company in companies:
            for article in COMPLIANCE_ARTICLES + DRONE_FIXES:
                _, created = ComplianceWatchItem.objects.get_or_create(
                    company=company,
                    law_reference=article["law_reference"],
                    description=article["description"],
                    defaults={
                        "status": article["status"],
                        "ai_notes": article["ai_notes"],
                        "deadline": timezone.now().date() + timedelta(days=90),
                        "last_checked": timezone.now(),
                    },
                )
                if created:
                    total_created += 1

            self.stdout.write(self.style.SUCCESS("{}: compliance artikli seeded".format(company.name)))

        self.stdout.write(
            self.style.SUCCESS("Ukupno kreirano: {} stavki za {} firmi".format(total_created, companies.count()))
        )
